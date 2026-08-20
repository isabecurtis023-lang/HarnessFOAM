import os
from fastapi import APIRouter
from fastapi.responses import FileResponse
from pydantic import BaseModel
import logging
logger = logging.getLogger(__name__)


router = APIRouter()

current_dir = os.path.dirname(os.path.abspath(__file__))
web_dir = os.path.join(os.path.dirname(current_dir), "web")

def safe_join(base_dir: str, requested_path: str) -> str:
    import os
    base_dir = os.path.abspath(base_dir)
    target_path = os.path.abspath(os.path.join(base_dir, requested_path.strip("/\\")))
    if not target_path.startswith(base_dir):
        raise ValueError("Directory traversal attempt blocked")
    return target_path

class SimulationRequest(BaseModel):
    prompt: str
    output_dir: str = "demo_run_web"


class AgentOptimizationRequest(BaseModel):
    base_case: str
    output_root: str
    user_objective: str

class OptimizationRequest(BaseModel):
    base_case: str
    output_root: str
    parameters: list
    objective: str = "last_time"
    direction: str = "max"


@router.get("/")
def read_root():
    return FileResponse(os.path.join(web_dir, "index.html"))

@router.get("/api/browse_folder")
def browse_folder():
    """Opens a native host OS folder picker dialog via a subprocess to avoid threading issues."""
    import subprocess
    import sys
    
    script = """
import tkinter as tk
from tkinter import filedialog
root = tk.Tk()
root.withdraw()
root.attributes("-topmost", True)
root.update()
folder_path = filedialog.askdirectory(parent=root, title="Select Project Output Directory")
root.destroy()
print(folder_path, end="")
"""
    try:
        result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60)
        folder_path = result.stdout.strip()
    except Exception as e:
        folder_path = ""
        logger.info(f"Error opening folder dialog: {e}")
        
    return {"path": folder_path}

@router.get("/api/models")
async def get_models(api_base: str = "", api_key: str = ""):
    """Fetches available models from an OpenAI-compatible /models endpoint."""
    import httpx
    
    if not api_base:
        return {"models": [], "error": "API Base URL is required"}
        
    # Standardize the endpoint url
    url = api_base.rstrip("/")
    if not url.endswith("/models"):
        url = url + "/models"
        
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
        models = [m.get("id") for m in data.get("data", []) if m.get("id")]
        return {"models": models, "error": None}
    except Exception as e:
        return {"models": [], "error": str(e)}


@router.get("/api/files")
def list_files(path: str = ""):
    """Lists files and directories for a given path."""
    import os
    if ".." in path.replace("\\", "/"):
        return {"error": "Directory traversal attempt blocked", "items": []}
    if not path or not os.path.exists(path):
        return {"error": "Invalid or non-existent path", "items": []}
    
    try:
        items = []
        for entry in os.scandir(path):
            items.append({
                "name": entry.name,
                "path": entry.path.replace("\\", "/"),
                "is_dir": entry.is_dir()
            })
        # Sort directories first, then alphabetically
        items.sort(key=lambda x: (not x["is_dir"], x["name"].lower()))
        return {"error": None, "items": items}
    except Exception as e:
        return {"error": str(e), "items": []}

@router.get("/api/file_content")
def get_file_content(path: str = ""):
    import os
    if ".." in path.replace("\\", "/"):
        return {"error": "Directory traversal attempt blocked", "content": ""}
    if not path or not os.path.isfile(path):
        return {"error": "File not found or is a directory", "content": ""}
    try:
        # Prevent very large files
        if os.path.getsize(path) > 10 * 1024 * 1024:
            return {"error": "File too large to display (max 10MB)", "content": ""}
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        return {"content": content, "error": None}
    except UnicodeDecodeError:
        return {"error": "Binary files are not supported for preview.", "content": ""}
    except Exception as e:
        return {"error": str(e), "content": ""}

@router.get("/api/check_env")
def check_env():
    import subprocess
    import shutil
    import importlib.util

    status = {"missing_libs": [], "wsl_missing_gmsh": False}
    
    # Check Python local libs
    required_libs = ["langgraph", "langchain", "openai", "pyvista", "matplotlib"]
    for lib in required_libs:
        if importlib.util.find_spec(lib) is None:
            status["missing_libs"].append(lib)
            
    # Check WSL gmsh
    if shutil.which("wsl"):
        try:
            res = subprocess.run(
                ["wsl", "python3", "-c", "import gmsh"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if res.returncode != 0:
                status["wsl_missing_gmsh"] = True
        except (subprocess.TimeoutExpired, OSError):
            # Environment probing must never leave the UI in a pending state.
            status["wsl_missing_gmsh"] = True

    return status

@router.post("/api/install_env")
def install_env():
    import subprocess
    import shutil
    import sys
    
    results = []
    
    # 1. Install local python deps if any
    try:
        req_file = os.path.join(os.path.dirname(current_dir), "requirements.txt")
        if os.path.exists(req_file):
            subprocess.run([sys.executable, "-m", "pip", "install", "-r", req_file], check=True)
            results.append("Local dependencies installed.")
    except Exception as e:
        results.append(f"Failed to install local deps: {e}")
        
    # 2. Install wsl gmsh
    if shutil.which("wsl"):
        try:
            subprocess.run(["wsl", "python3", "-m", "pip", "install", "gmsh", "--break-system-packages"], check=True)
            results.append("WSL gmsh installed.")
        except Exception as e:
            results.append(f"Failed to install WSL gmsh: {e}")
            
    return {"message": " ".join(results)}

class SaveFileRequest(BaseModel):
    path: str
    content: str

class AssistantPatchRequest(BaseModel):
    path: str
    content: str = ""
    confirm: bool = False

class GitHubFeedbackRequest(BaseModel):
    kind: str = "issue"
    title: str
    body: str
    base: str = "master"
    confirm: bool = False

class AssistantRepairRequest(BaseModel):
    output_dir: str = "tmp_assistant_cavity_repair"
    confirm: bool = False
    execute: bool = False

class MemoryClearRequest(BaseModel):
    case_dir: str
    agent: str | None = None
    confirm: bool = False

@router.get("/api/assistant/memory")
def assistant_memory(case_dir: str, enabled: bool = False):
    from harnessfoam.memory import memory_snapshot
    return memory_snapshot(case_dir, enabled=enabled)

@router.post("/api/assistant/memory/clear")
def assistant_memory_clear(req: MemoryClearRequest):
    from harnessfoam.memory import clear_memory
    return clear_memory(req.case_dir, req.agent, confirm=req.confirm)

@router.post("/api/assistant/github-feedback")
def assistant_github_feedback(req: GitHubFeedbackRequest):
    from harnessfoam.github_feedback import create_feedback
    return create_feedback(kind=req.kind, title=req.title, body=req.body,
                           base=req.base, confirm=req.confirm)

@router.get("/api/assistant/search")
def assistant_search(q: str):
    from harnessfoam.assistant_tools import search_files
    return {"results": search_files(q)}

@router.get("/api/assistant/read")
def assistant_read(path: str):
    from harnessfoam.assistant_tools import read_file
    try: return read_file(path)
    except Exception as exc: return {"error": str(exc)}

@router.get("/api/assistant/log")
def assistant_log(path: str):
    from harnessfoam.assistant_tools import analyze_log
    try: return analyze_log(path)
    except Exception as exc: return {"error": str(exc)}

@router.post("/api/assistant/patch")
def assistant_patch(req: AssistantPatchRequest):
    from harnessfoam.assistant_tools import apply_patch
    try: return apply_patch(req.path, req.content, confirm=req.confirm)
    except Exception as exc: return {"status": "ERROR", "error": str(exc)}

@router.post("/api/assistant/tests")
def assistant_tests():
    from harnessfoam.assistant_tools import run_unit_tests
    return run_unit_tests()

@router.post("/api/assistant/cavity")
def assistant_cavity(output_dir: str = "tmp_assistant_cavity"):
    from harnessfoam.assistant_tools import run_cavity_benchmark
    return run_cavity_benchmark(output_dir)

@router.get("/api/benchmark/interface-matrix")
def benchmark_interface_matrix(include_tutorials: bool = False):
    from harnessfoam.benchmark_matrix import run_interface_matrix
    return run_interface_matrix(include_tutorials=include_tutorials)

@router.post("/api/assistant/cavity-repair")
def assistant_cavity_repair(output_dir: str = "tmp_assistant_cavity_repair", execute: bool = False):
    from harnessfoam.cavity_repair import run_cavity_repair_scenario
    return run_cavity_repair_scenario(output_dir, execute=execute)

@router.post("/api/assistant/repair")
def assistant_repair(req: AssistantRepairRequest):
    """Two-phase, deterministic repair workflow for the Web Assistant."""
    from harnessfoam.cavity_repair import run_cavity_repair_scenario
    try:
        return run_cavity_repair_scenario(req.output_dir, confirm=req.confirm, execute=req.execute)
    except Exception as exc:
        return {"status": "FAILED", "stage": "assistant_repair", "error": str(exc)}

@router.post("/api/save_file")
def save_file(req: SaveFileRequest):
    import os
    if ".." in req.path.replace("\\", "/"):
        return {"error": "Directory traversal attempt blocked"}
    if not req.path or not os.path.exists(req.path):
        return {"error": "File does not exist"}
    try:
        with open(req.path, "w", encoding="utf-8") as f:
            f.write(req.content)
        return {"success": True, "error": None}
    except Exception as e:
        return {"error": str(e)}

# 2026-08-15 – Gemini 3.5 Flash: File Operations API Models and Handlers
class DeleteRequest(BaseModel):
    path: str

class RenameRequest(BaseModel):
    path: str
    new_name: str

class CopyPasteRequest(BaseModel):
    src_path: str
    dest_dir: str

class CreateRequest(BaseModel):
    parent_path: str
    name: str
    is_dir: bool

@router.post("/api/delete_file")
def delete_file(req: DeleteRequest):
    import os
    import shutil
    path = req.path
    if ".." in path.replace("\\", "/"):
        return {"status": "error", "message": "Directory traversal attempt blocked"}
    if not os.path.exists(path):
        return {"status": "error", "message": "File or directory does not exist"}
    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
        else:
            os.remove(path)
        return {"status": "ok"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/api/rename_file")
def rename_file(req: RenameRequest):
    import os
    path = req.path
    new_name = req.new_name
    if ".." in path.replace("\\", "/") or ".." in new_name.replace("\\", "/"):
        return {"status": "error", "message": "Directory traversal attempt blocked"}
    if not os.path.exists(path):
        return {"status": "error", "message": "Source path does not exist"}
    parent = os.path.dirname(path)
    new_path = os.path.join(parent, new_name)
    if os.path.exists(new_path):
        return {"status": "error", "message": "A file or folder with that name already exists"}
    try:
        os.rename(path, new_path)
        return {"status": "ok", "new_path": new_path}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/api/copy_paste_file")
def copy_paste_file(req: CopyPasteRequest):
    import os
    import shutil
    src = req.src_path
    dest_dir = req.dest_dir
    if ".." in src.replace("\\", "/") or ".." in dest_dir.replace("\\", "/"):
        return {"status": "error", "message": "Directory traversal attempt blocked"}
    if not os.path.exists(src):
        return {"status": "error", "message": "Source path does not exist"}
    if not os.path.exists(dest_dir) or not os.path.isdir(dest_dir):
        return {"status": "error", "message": "Destination folder does not exist"}
        
    name = os.path.basename(src)
    dest_path = os.path.join(dest_dir, name)
    
    # Avoid overwriting
    base, ext = os.path.splitext(name)
    counter = 1
    while os.path.exists(dest_path):
        new_name = f"{base}_copy{counter}{ext}" if not os.path.isdir(src) else f"{name}_copy{counter}"
        dest_path = os.path.join(dest_dir, new_name)
        counter += 1
        
    try:
        if os.path.isdir(src):
            shutil.copytree(src, dest_path)
        else:
            shutil.copy2(src, dest_path)
        return {"status": "ok", "new_path": dest_path}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/api/create_item")
def create_item(req: CreateRequest):
    import os
    parent = req.parent_path
    name = req.name
    is_dir = req.is_dir
    
    if ".." in parent.replace("\\", "/") or ".." in name.replace("\\", "/"):
        return {"status": "error", "message": "Directory traversal attempt blocked"}
    
    if not os.path.exists(parent) or not os.path.isdir(parent):
        return {"status": "error", "message": "Parent directory does not exist"}
        
    target_path = os.path.join(parent, name)
    if os.path.exists(target_path):
        return {"status": "error", "message": "Item with this name already exists"}
        
    try:
        if is_dir:
            os.makedirs(target_path, exist_ok=True)
        else:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write("")
        return {"status": "ok", "path": target_path}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.get("/api/cwd")
def get_cwd():
    import os
    return {"cwd": os.getcwd().replace("\\", "/")}

@router.get("/api/knowledge_status")
def knowledge_status():
    """Expose the local RAG corpus state to the Web UI and diagnostics."""
    from harnessfoam.knowledge import official_tutorial_stats
    return official_tutorial_stats()


@router.post("/api/agent_optimize")
def agent_optimize_case(req: AgentOptimizationRequest):
    """Run an intelligent, LLM-driven parameter sweep based on natural language."""
    from harnessfoam.agents.optimizer import run_agentic_optimization
    return run_agentic_optimization(req.base_case, req.output_root, req.user_objective)

@router.post("/api/optimize")
def optimize_case(req: OptimizationRequest):
    """Run a bounded OpenFOAM 13 parameter sweep."""
    from harnessfoam.optimization import run_parameter_sweep
    return run_parameter_sweep(req.base_case, req.output_root, req.parameters, objective=req.objective, direction=req.direction)

@router.get("/api/system_status")
def system_status():
    import subprocess
    import shutil
    
    status = {"openfoam": False, "method": ""}
    
    # Check 1: Native Windows (BlueCFD or similar in PATH)
    if shutil.which("blockMesh"):
        status["openfoam"] = True
        status["method"] = "Native"
        return status
        
    # Check 2: WSL
    if shutil.which("wsl"):
        try:
            res = subprocess.run(["wsl", "bash", "-lc", ". /opt/openfoam13/etc/bashrc >/dev/null 2>&1 && command -v blockMesh"], capture_output=True, text=True, timeout=15)
            if res.returncode == 0 and res.stdout.strip():
                status["openfoam"] = True
                status["method"] = "WSL"
                return status
        except Exception:
            pass
            
    return status

@router.get("/api/llm_status")
async def llm_status(api_base: str = "", api_key: str = ""):
    import os
    import httpx
    
    # 2026-08-15 – Claude Opus 4.6: fix env var names to match .env file
    base = api_base or os.getenv("OPENAI_API_BASE", "")
    key = api_key or os.getenv("OPENAI_API_KEY", "")
    
    if not base:
        return {"status": "error", "message": "API Base URL missing"}
        
    url = base.rstrip("/")
    if not url.endswith("/models"):
        url = url + "/models"
        
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=5)
            response.raise_for_status()
        return {"status": "ok", "message": "API Responding"}
    except Exception as e:
        return {"status": "error", "message": "Connection Failed"}

