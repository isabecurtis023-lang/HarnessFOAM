import asyncio
from harnessfoam.agents.graph import create_workflow, SimulationState

async def run():
    print("Starting generation...")
    workflow = create_workflow()
    initial_state = SimulationState(
        user_requirement="Simulate a 2D lid-driven cavity flow. The top wall moves at 1 m/s in the x-direction. The domain is a 0.1m x 0.1m square.",
        case_dir="C:/Users/Administrator/Desktop/temp/TEST",
        llm_kwargs={"temperature": 0.1},
        max_errors=3
    )
    
    async for output in workflow.astream(initial_state):
        for node_name, state in output.items():
            print(f"Finished node: {node_name}")
            if node_name == "reviewer":
                print(f"Reviewer suggestions: {state['logs'].get('review_suggestions')}")
            if node_name == "end":
                print("Workflow reached END node.")
                return

asyncio.run(run())
