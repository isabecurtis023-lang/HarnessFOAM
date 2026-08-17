import os
from typing import Dict
import shutil
from mcp.server.fastmcp import FastMCP

app = FastMCP("HarnessFOAM-MCP")
_jobs: Dict[str, dict] = {}

# Tools definitions
@app.tool()
async def create_case(user_prompt: str) -> dict:
    """Initializes a new CFD simulation case and its workspace."""
    case_id = "case_" + os.urandom(4).hex()
    case_dir = os.path.abspath(os.path.join("mcp_cases", case_id))
    os.makedirs(case_dir, exist_ok=True)
    _jobs[case_id] = {"case_id": case_id, "case_dir": case_dir, "prompt": user_prompt, "status": "CREATED", "logs": {}}
    return {"case_id": case_id, "case_dir": case_dir, "status": "CREATED"}

from harnessfoam.agents.architect import plan_simulation
from harnessfoam.agents.input_writer import write_simulation_inputs

@app.tool()
async def plan_simulation_structure(case_id: str, user_prompt: str) -> dict:
    """Plans the required file and directory structure based on the user prompt."""
    plan = plan_simulation(user_prompt)
    return {"plan": plan}

@app.tool()
async def generate_file_content(case_id: str, file: str, folder: str, user_prompt: str) -> dict:
    """Generates the content for a single specified configuration file."""
    # To keep it simple, we wrap it into the plan format expected by input writer
    generated = write_simulation_inputs([{"file": file, "folder": folder}], user_prompt)
    return {"content": generated.get(f"{folder}/{file}", "")}

from harnessfoam.agents.meshing import generate_mesh_script
from harnessfoam.agents.visualizer import generate_visualization_script

@app.tool()
async def generate_mesh(case_id: str, mesh_config: dict, user_prompt: str) -> dict:
    """Asynchronously generates the computational mesh using a specified method."""
    mesh_res = generate_mesh_script(user_prompt)
    return {
        "job_id": f"mesh_{case_id}", 
        "is_gmsh": mesh_res.get("is_gmsh_required", False),
        "script": mesh_res.get("python_script", "")
    }

from harnessfoam.agents.runner import generate_hpc_script
from harnessfoam.agents.reviewer import analyze_errors

@app.tool()
async def generate_hpc_script_tool(case_id: str, hpc_config: dict, user_prompt: str) -> dict:
    """Generates a job submission script (e.g., Slurm) for a high-performance computing cluster."""
    script = generate_hpc_script(user_prompt)
    return {"script_content": script}

@app.tool()
async def run_simulation(case_id: str, environment: str) -> dict:
    """Executes the local workflow and returns a real job snapshot.

    Remote/HPC submission is intentionally not implemented in this P0 pass;
    callers receive an explicit status instead of a fabricated SUCCESS.
    """
    job_id = f"run_{case_id}"
    job = _jobs.get(case_id)
    if not job:
        return {"job_id": job_id, "status": "FAILED", "error": "Unknown case_id"}
    if environment.lower() not in ("local", "native", "wsl", "auto"):
        job.update(status="UNSUPPORTED", error="Remote/HPC execution is not enabled")
        return {"job_id": job_id, "status": job["status"], "error": job["error"]}
    workflow = __import__("harnessfoam.agents.graph", fromlist=["create_workflow", "SimulationState"])
    graph = workflow.create_workflow()
    state = workflow.SimulationState(user_requirement=job["prompt"], case_dir=job["case_dir"], max_errors=3)
    try:
        final_state = await graph.ainvoke(state)
        job.update(status=final_state.get("status", "UNKNOWN"), logs=final_state.get("logs", {}), state=final_state)
    except Exception as exc:
        job.update(status="FAILED", logs={"execution_error": str(exc)})
    return {"job_id": job_id, "status": job["status"], "case_id": case_id, "metrics": job["logs"].get("runtime_metrics", {})}

@app.tool()
async def check_job_status(job_id: str) -> dict:
    """Checks the status of any asynchronous job (meshing, simulation, visualization)."""
    case_id = job_id.removeprefix("run_")
    job = _jobs.get(case_id)
    if not job:
        return {"status": {"state": "UNKNOWN", "error": "Unknown job_id"}}
    return {"status": {"state": job.get("status", "UNKNOWN"), "case_id": case_id, "metrics": job.get("logs", {}).get("runtime_metrics", {})}}

@app.tool()
async def get_simulation_logs(case_id: str, job_id: str) -> dict:
    """Retrieves detailed logs for a failed job to enable error diagnosis."""
    job = _jobs.get(case_id, {})
    return {"logs": job.get("logs", {})}

@app.tool()
async def review_and_suggest_fix(case_id: str, logs: dict) -> dict:
    """Analyzes error logs and proposes corrective actions."""
    error_text = logs.get("error", "")
    analysis = analyze_errors(error_text)
    return {"suggestions": analysis.get("suggestions", [])}

@app.tool()
async def apply_fix(case_id: str, modifications: list) -> dict:
    """Apply content patches safely, preserving a backup for every file."""
    job = _jobs.get(case_id)
    if not job:
        return {"status": "FAILED", "error": "Unknown case_id"}
    case_dir = os.path.abspath(job["case_dir"])
    backup_dir = os.path.join(case_dir, ".harnessfoam", "backups", "mcp_fix")
    applied = []
    errors = []
    for modification in modifications or []:
        if not isinstance(modification, dict):
            errors.append("Each modification must be an object")
            continue
        relative = modification.get("path")
        if not relative and modification.get("folder") and modification.get("file"):
            relative = os.path.join(modification["folder"], modification["file"])
        content = modification.get("content")
        if not relative or not isinstance(content, str):
            errors.append("Each modification requires path and string content")
            continue
        target = os.path.abspath(os.path.join(case_dir, str(relative)))
        try:
            if os.path.commonpath([case_dir, target]) != case_dir:
                raise ValueError("path escapes the case directory")
        except ValueError as exc:
            errors.append(f"Rejected {relative}: {exc}")
            continue
        if os.path.isfile(target):
            backup_target = os.path.join(backup_dir, os.path.relpath(target, case_dir))
            os.makedirs(os.path.dirname(backup_target), exist_ok=True)
            shutil.copy2(target, backup_target)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
        applied.append(os.path.relpath(target, case_dir).replace("\\", "/"))
    if errors:
        return {"status": "FAILED", "applied": applied, "errors": errors}
    job["status"] = "FIX_APPLIED"
    job["logs"] = {**job.get("logs", {}), "mcp_fix_backup": backup_dir, "mcp_fix_files": applied}
    return {"status": "REQUIRES_WORKFLOW_RETRY", "applied": applied, "backup_dir": backup_dir, "message": "Fix applied; run the case again to re-run preflight and solver validation."}

@app.tool()
async def generate_visualization(case_id: str, quantity: str, user_prompt: str) -> dict:
    """Asynchronously generates a visualization of the simulation results."""
    viz_res = generate_visualization_script(user_prompt)
    return {
        "job_id": f"viz_{case_id}",
        "is_viz": viz_res.get("is_visualization_required", False),
        "script": viz_res.get("pyvista_script", "")
    }
