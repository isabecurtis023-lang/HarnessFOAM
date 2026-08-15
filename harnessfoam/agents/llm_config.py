import os
from langchain_openai import ChatOpenAI
from langchain_core.language_models import BaseChatModel

def build_llm(temperature: float = 0.0) -> BaseChatModel:
    """
    Universally builds the LLM based on environment configurations.
    Defaults to OpenAI compatible interface.
    """
    provider = os.getenv("LLM_PROVIDER", "openai").lower()
    
    if provider == "openai":
        return ChatOpenAI(
            model=os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
            temperature=temperature,
            api_key=os.getenv("OPENAI_API_KEY"),
            base_url=os.getenv("OPENAI_API_BASE")
        )
    # Extensible for Anthropic, Bedrock, etc.
    elif provider == "anthropic":
        try:
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model_name=os.getenv("LLM_MODEL", "claude-3-5-sonnet-20240620"),
                temperature=temperature,
                anthropic_api_key=os.getenv("ANTHROPIC_API_KEY")
            )
        except ImportError:
            raise ImportError("Please install langchain-anthropic to use Anthropic models.")
    else:
        raise ValueError(f"Unsupported LLM provider: {provider}")
