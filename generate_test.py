import asyncio
from harnessfoam.agents.graph import create_workflow, SimulationState

async def run():
    print("Starting generation...")
    workflow = create_workflow()
    initial_state = SimulationState(
        user_requirement="Simulate incompressible flow over a circular cylinder at 2 m/s. Use a 2D domain. The cylinder radius is 0.05m.",
        case_dir="C:/Users/Administrator/Desktop/temp/TEST",
        llm_kwargs={"temperature": 0.1},
        max_errors=3
    )
    
    async for output in workflow.astream(initial_state):
        for node_name, state in output.items():
            print(f"Finished node: {node_name}")
            if node_name == "input_writer":
                # We stop after input_writer so we don't trigger Runner which takes time
                print("Files generated successfully in TEST directory. Exiting.")
                return

asyncio.run(run())
