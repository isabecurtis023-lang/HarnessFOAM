import asyncio
import os
from harnessfoam.agents.visualizer import build_visualizer_agent
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

def test_prompt():
    print("Testing visualizer agent prompt with gpt-3.5-turbo...")
    llm_kwargs = {"model": "gpt-3.5-turbo"}
    
    try:
        chain = build_visualizer_agent(llm_kwargs=llm_kwargs)
        result = chain.invoke({"user_requirement": "Plot the velocity magnitude and save as PNG."})
        print("SUCCESS! Result:", result)
    except Exception as e:
        print("FAILED!")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_prompt()
