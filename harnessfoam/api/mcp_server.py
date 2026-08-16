import os
import asyncio
from mcp.server.fastmcp import FastMCP

from harnessfoam.agents.graph import create_workflow, SimulationState

# Create the FastMCP server
mcp = FastMCP("HarnessFOAM")

@mcp.tool()
async def get_knowledge_status() -> str:
    """Return the indexed official OpenFOAM tutorial corpus status."""
    import json
    from harnessfoam.knowledge import official_tutorial_stats
    return json.dumps(official_tutorial_stats(), ensure_ascii=False)

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
                
        logs = final_state.get("logs", {})
        status = final_state.get("status", "UNKNOWN")
        metrics = logs.get("runtime_metrics", {})
        return (
            f"Simulation workflow status: {status}\n"
            f"Output Directory: {os.path.abspath(output_dir)}\n"
            f"Preflight: {logs.get('preflight_ok', 'N/A')}\n"
            f"Post-process: {logs.get('postprocess_status', 'N/A')}\n"
            f"Runtime Metrics: {metrics}\n"
            f"Errors: {logs.get('execution_error', '')}\n"
            f"{files_summary}"
        )
    except Exception as e:
        return f"Error executing CFD simulation: {str(e)}"

def start_mcp():
    """Starts the FastMCP server using stdio transport."""
    mcp.run(transport='stdio')
