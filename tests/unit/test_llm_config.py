import pytest
import os
import json
from unittest.mock import patch, MagicMock
from pydantic import BaseModel

from harnessfoam.agents.llm_config import build_llm, DeepSeekRobustParser, create_structured_chain

class DummyModel(BaseModel):
    name: str
    value: int

def test_build_llm_openai_default():
    with patch.dict(os.environ, {"LLM_PROVIDER": "openai", "OPENAI_API_KEY": "test-key"}):
        llm = build_llm(temperature=0.5)
        # Check if the class name contains ChatOpenAI
        assert "ChatOpenAI" in str(type(llm))
        assert llm.temperature == 0.5
        
def test_build_llm_anthropic():
    with patch.dict(os.environ, {"LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "test-key"}):
        try:
            llm = build_llm(temperature=0.2)
            assert "ChatAnthropic" in str(type(llm))
            assert llm.temperature == 0.2
        except ImportError:
            # If langchain-anthropic is not installed in the environment, it should raise ImportError
            pass

def test_build_llm_unsupported_provider():
    with pytest.raises(ValueError, match="Unsupported LLM provider: unknown"):
        build_llm(provider="unknown")

def test_deepseek_robust_parser_clean():
    parser = DeepSeekRobustParser(pydantic_object=DummyModel)
    raw_text = '{"name": "test", "value": 42}'
    parsed = parser.parse(raw_text)
    assert parsed.name == "test"
    assert parsed.value == 42

def test_deepseek_robust_parser_with_think_tags():
    parser = DeepSeekRobustParser(pydantic_object=DummyModel)
    raw_text = '<think> I am thinking \n very hard </think>\n```json\n{"name": "test2", "value": 99}\n```'
    parsed = parser.parse(raw_text)
    assert parsed.name == "test2"
    assert parsed.value == 99

def test_create_structured_chain():
    # Mock LLM and prompt
    from langchain_core.prompts import PromptTemplate
    prompt = PromptTemplate.from_template("Hello {input}")
    
    # Just checking if the chain is constructed without error
    chain = create_structured_chain(MagicMock(), prompt, DummyModel)
    assert chain is not None
