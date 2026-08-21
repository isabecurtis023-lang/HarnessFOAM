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
async def run_parameter_optimization(base_case: str, output_root: str, parameters: list, objective: str = "last_time", direction: str = "max") -> str:
    """Run a bounded OpenFOAM 13 parameter grid and return the best result."""
    import json
    from harnessfoam.optimization import run_parameter_sweep
    result = run_parameter_sweep(base_case, output_root, parameters, objective=objective, direction=direction)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def run_agentic_optimization(base_case: str, output_root: str, user_objective: str) -> str:
    """Run an intelligent, LLM-driven parameter sweep based on natural language."""
    import json
    from harnessfoam.agents.optimizer import run_agentic_optimization as agent_opt
    result = agent_opt(base_case, output_root, user_objective)
    return json.dumps(result, ensure_ascii=False)

@mcp.tool()
async def run_cavity_benchmark(output_dir: str = "tmp_mcp_cavity") -> str:
    """Run the deterministic OpenFOAM 13 cavity smoke benchmark."""
    import json
    from harnessfoam.benchmark import run_cavity_smoke
    return json.dumps(run_cavity_smoke(output_dir), ensure_ascii=False)

@mcp.tool()
async def run_cavity_repair_benchmark(output_dir: str = "tmp_mcp_cavity_repair", execute: bool = False) -> str:
    """Inject a cavity patch error, preview/apply a deterministic fix, and revalidate it."""
    import json
    from harnessfoam.cavity_repair import run_cavity_repair_scenario
    return json.dumps(run_cavity_repair_scenario(output_dir, execute=execute), ensure_ascii=False)

@mcp.tool()
async def search_repository(query: str) -> str:
    """Search repository source files for an assistant diagnostic query."""
    import json
    from harnessfoam.assistant_tools import search_files
    return json.dumps({"results": search_files(query)}, ensure_ascii=False)

@mcp.tool()
async def read_repository_file(path: str) -> str:
    """Read one repository file within the HarnessFOAM root."""
    import json
    from harnessfoam.assistant_tools import read_file
    try:
        return json.dumps(read_file(path), ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

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
            f"Physics Metrics: {logs.get('physics_metrics', {})}\n"
            f"Benchmark Metrics: {logs.get('benchmark_metrics', {})}\n"
            f"Failure Ledger: {logs.get('failure_ledger_summary', {})}\n"
            f"Post-process Metrics: {logs.get('postprocess_metrics', {})}\n"
            f"Errors: {logs.get('execution_error', '')}\n"
            f"{files_summary}"
        )
    except Exception as e:
        return f"Error executing CFD simulation: {str(e)}"

def start_mcp():
    """Starts the FastMCP server using stdio transport."""
    mcp.run(transport='stdio')
