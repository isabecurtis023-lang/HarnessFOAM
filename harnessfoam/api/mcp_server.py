import os
import asyncio
from mcp.server.fastmcp import FastMCP

from harnessfoam.agents.graph import create_workflow, SimulationState

# Create the FastMCP server
mcp = FastMCP("HarnessFOAM")

@mcp.tool()
async def run_cfd_simulation(prompt: str, output_dir: str = "demo_run_mcp") -> str:
    """
    Executes a complete AI-driven Computational Fluid Dynamics (CFD) workflow using OpenFOAM.
    
    Args:
        prompt: A natural language description of the fluid dynamics problem (e.g., 'Simulate incompressible flow over a cylinder at 2 m/s')
        output_dir: The directory where the OpenFOAM case files should be generated and executed.
    
    Returns:
        A string summarizing the generated files, execution status, and the final output directory.
    """
    workflow = create_workflow()
    initial_state = SimulationState(
        user_requirement=prompt,
        case_dir=output_dir,
    )
    
    try:
        final_state = await workflow.ainvoke(initial_state)
        
        # Build a summary of the generated files
        files_summary = ""
        if final_state.get("file_plan"):
            files_summary = "\nGenerated Files:\n"
            for f in final_state["file_plan"]:
                files_summary += f"- {f['folder']}/{f['file']}\n"
                
        return (
            f"Simulation workflow completed successfully!\n"
            f"Output Directory: {os.path.abspath(output_dir)}\n"
            f"{files_summary}"
        )
    except Exception as e:
        return f"Error executing CFD simulation: {str(e)}"

def start_mcp():
    """Starts the FastMCP server using stdio transport."""
    mcp.run(transport='stdio')
