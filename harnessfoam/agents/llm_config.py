import os
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

def build_llm(temperature: float = 0.0, **kwargs) -> BaseChatModel:
    """
    Universally builds the LLM based on environment configurations or explicit runtime kwargs.
    Defaults to OpenAI compatible interface.
    """
    # Runtime kwargs take precedence over .env variables
    provider = kwargs.get("provider", os.getenv("LLM_PROVIDER", "openai")).lower()
    callbacks = kwargs.get("callbacks", None)
    
    if provider == "openai":
        # 2026-08-15 – Claude Opus 4.6 (Thinking): increased timeout for slow TechCloud models
        return ChatOpenAI(
            model=kwargs.get("model") or os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
            temperature=temperature,
            api_key=kwargs.get("api_key") or os.getenv("OPENAI_API_KEY") or "dummy",
            base_url=kwargs.get("base_url") or os.getenv("OPENAI_API_BASE"),
            timeout=600,    # 10 min – thinking models on TechCloud can be very slow
            max_retries=2,
            streaming=True,  # keep connection alive during long generation
            callbacks=callbacks
        )
    # Extensible for Anthropic, Bedrock, etc.
    elif provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model_name=kwargs.get("model") or os.getenv("LLM_MODEL", "claude-3-5-sonnet-20240620"),
                temperature=temperature,
                anthropic_api_key=kwargs.get("api_key") or os.getenv("ANTHROPIC_API_KEY"),
                callbacks=callbacks
            )
        except ImportError:
            raise ImportError("Please install langchain-anthropic to use Anthropic models.")
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")

import re
import json
from langchain_core.output_parsers import BaseOutputParser
from langchain_core.exceptions import OutputParserException
from typing import Type, Any
from pydantic import BaseModel

class DeepSeekRobustParser(BaseOutputParser):
    pydantic_object: Type[BaseModel]

    def parse(self, text: str) -> Any:
        # Strip <think>...</think> block if it exists
        text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
        
        # Helper to extract all top-level JSON objects/arrays
        def extract_json_objects(s):
            objects = []
            depth = 0
            start = -1
            in_string = False
            escape = False
            for i, c in enumerate(s):
                if c == '"' and not escape:
                    in_string = not in_string
                elif not in_string:
                    if c in '{[':
                        if depth <= 0:
                            start = i
                            depth = 0
                        depth += 1
                    elif c in '}]':
                        depth -= 1
                        if depth == 0 and start != -1:
                            objects.append(s[start:i+1])
                            start = -1
                        elif depth < 0:
                            depth = 0
                if c == '\\' and not escape:
                    escape = True
                else:
                    escape = False
            return objects

        candidates = extract_json_objects(text)
        
        last_exception = None
        # Models usually output the real answer at the end, so we check in reverse order
        for cand in reversed(candidates):
            try:
                parsed = json.loads(cand)
                # Handle cases where model wraps the actual answer in an 'instance' key inside the schema
                if isinstance(parsed, dict) and "properties" in parsed and "instance" in parsed:
                    if isinstance(parsed["instance"], dict):
                        parsed = parsed["instance"]
                return self.pydantic_object.model_validate(parsed)
            except Exception as e:
                last_exception = e
                
        # Fallback to basic stripping if bracket extraction failed or returned nothing valid
        try:
            text_clean = text.strip()
            if text_clean.startswith("```json"): text_clean = text_clean[7:]
            elif text_clean.startswith("```"): text_clean = text_clean[3:]
            if text_clean.endswith("```"): text_clean = text_clean[:-3]
            parsed = json.loads(text_clean.strip())
            if isinstance(parsed, dict) and "properties" in parsed and "instance" in parsed:
                if isinstance(parsed["instance"], dict):
                    parsed = parsed["instance"]
            return self.pydantic_object.model_validate(parsed)
        except Exception as e:
            raise OutputParserException(f"Failed to parse JSON. Last error: {last_exception or e}\nRaw text: {text}")

def create_structured_chain(llm, prompt, pydantic_schema, example_json_str=None):
    """
    Creates a robust chain for extracting structured data, handling models that 
    may output <think> tags or refuse native function calling.
    """
    schema_json = json.dumps(pydantic_schema.model_json_schema())
    schema_json_escaped = schema_json.replace("{", "{{").replace("}", "}}")
    
    example_block = ""
    if example_json_str:
        example_json_escaped = example_json_str.replace("{", "{{").replace("}", "}}")
        example_block = f"\nExample Output:\n{example_json_escaped}\n"

    format_instructions = f"""

====================
OUTPUT FORMAT INSTRUCTIONS:
You must output ONLY a valid JSON object containing your actual generated data. 
CRITICAL: DO NOT output the schema itself! I am providing the schema below so you know what fields are required, but you must return a JSON instance with ACTUAL VALUES populated for this specific case.
JSON Schema to follow:
{schema_json_escaped}
{example_block}
Remember: Output ONLY the raw JSON data object. No markdown, no explanations."""
    
    # Append instructions to prompt
    from langchain_core.prompts import PromptTemplate
    new_template = prompt.template + format_instructions
    new_prompt = PromptTemplate(
        template=new_template,
        input_variables=prompt.input_variables
    )
    
    parser = DeepSeekRobustParser(pydantic_object=pydantic_schema)
    return new_prompt | llm | parser
