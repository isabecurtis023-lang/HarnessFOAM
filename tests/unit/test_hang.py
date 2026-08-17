import asyncio
import os
from dotenv import load_dotenv
load_dotenv()
from harnessfoam.agents.visualizer import generate_visualization_script
from harnessfoam.api.server import WebSocketStreamingCallbackHandler

class DummyWebsocket:
    def send_json(self, data):
        print("WS SEND:", data)
        return asyncio.sleep(0)

async def test_postprocess():
    loop = asyncio.get_running_loop()
    ws = DummyWebsocket()
    llm_kwargs = {"callbacks": [WebSocketStreamingCallbackHandler(ws, "TestAgent")]}
    
    # We must mock api_base since it comes from UI usually, but here we just rely on .env
    print("STARTING LLM CALL with OPENAI_API_BASE=", os.getenv("OPENAI_API_BASE"))
    import functools
    func = functools.partial(generate_visualization_script, "Plot the velocity magnitude and save as PNG.", llm_kwargs=llm_kwargs)
    try:
        viz_results = await loop.run_in_executor(None, func)
        print("LLM CALL FINISHED! Results:", viz_results)
    except Exception as e:
        print("LLM CALL FAILED:", repr(e))
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_postprocess())
