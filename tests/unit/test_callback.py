import asyncio
from harnessfoam.agents.llm_config import build_llm, create_structured_chain
from langchain_core.prompts import PromptTemplate
from harnessfoam.agents.visualizer import VisualizationScriptResult
from langchain_core.callbacks import BaseCallbackHandler

class MockHandler(BaseCallbackHandler):
    def on_llm_new_token(self, token: str, **kwargs):
        print(token, end="", flush=True)
    def on_llm_end(self, response, **kwargs):
        print("\n\nLLM END")

def test_chain():
    llm = build_llm(model="gpt-3.5-turbo", streaming=True, callbacks=[MockHandler()])
    prompt = PromptTemplate(template="Say hello and output a short json.", input_variables=[])
    chain = create_structured_chain(llm, prompt, VisualizationScriptResult)
    print("Invoking...")
    res = chain.invoke({})
    print("Result:", res)

if __name__ == "__main__":
    test_chain()
