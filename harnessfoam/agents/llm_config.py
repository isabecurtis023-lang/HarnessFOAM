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
        # 2026-08-15 – Claude Opus 4.6 (Thinking): increased timeout for slow 科技云 models
        return ChatOpenAI(
            model=kwargs.get("model") or os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
            temperature=temperature,
            api_key=kwargs.get("api_key") or os.getenv("OPENAI_API_KEY") or "dummy",
            base_url=kwargs.get("base_url") or os.getenv("OPENAI_API_BASE"),
            timeout=600,    # 10 min – thinking models on 科技云 can be very slow
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
        
        # Strip ```json ... ``` blocks
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
            
        text = text.strip()
        
        # Try to find JSON object or array
        match = re.search(r'(\{.*\})|(\[.*\])', text, re.DOTALL)
        if match:
            text = match.group(0)
            
        try:
            parsed = json.loads(text)
            return self.pydantic_object.model_validate(parsed)
        except Exception as e:
            raise OutputParserException(f"Failed to parse JSON: {e}\nRaw text: {text}")

def create_structured_chain(llm, prompt, pydantic_schema):
    """
    Creates a robust chain for extracting structured data, handling models that 
    may output <think> tags or refuse native function calling.
    """
    schema_json = json.dumps(pydantic_schema.model_json_schema())
    schema_json_escaped = schema_json.replace("{", "{{").replace("}", "}}")
    
    format_instructions = (
        "\n\nIMPORTANT: You must respond ONLY with valid JSON matching this schema. "
        "Do not include any explanation, markdown formatting, or <think> tags. Just the JSON object:\n"
        f"{schema_json_escaped}"
    )
    
    # Append instructions to prompt
    from langchain_core.prompts import PromptTemplate
    new_template = prompt.template + format_instructions
    new_prompt = PromptTemplate(
        template=new_template,
        input_variables=prompt.input_variables
    )
    
    parser = DeepSeekRobustParser(pydantic_object=pydantic_schema)
    return new_prompt | llm | parser
