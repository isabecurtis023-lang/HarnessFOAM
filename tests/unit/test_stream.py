import asyncio
from harnessfoam.agents.visualizer import generate_visualization_script
import functools

async def main():
    loop = asyncio.get_running_loop()
    print("Starting generator...")
    func = functools.partial(generate_visualization_script, "Visualize U")
    res = await loop.run_in_executor(None, func)
    print("DONE:", res)

if __name__ == "__main__":
    asyncio.run(main())
