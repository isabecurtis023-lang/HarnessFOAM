import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
from harnessfoam.agents.graph import create_workflow, SimulationState
from langchain_core.callbacks import AsyncCallbackHandler

class WebSocketStreamingCallbackHandler(AsyncCallbackHandler):
    def __init__(self, websocket: WebSocket, agent_name: str = "LLM"):
        self.websocket = websocket
        self.agent_name = agent_name

    async def on_chat_model_start(self, serialized: dict, messages: list, **kwargs):
        # Extract prompt from messages
        prompt_text = "\n".join([m.content for m in messages[0]]) if messages and messages[0] else ""
        try:
            await self.websocket.send_json({
                "type": "llm_start",
                "agent": self.agent_name,
                "prompt": prompt_text
            })
        except Exception:
            pass

    async def on_llm_new_token(self, token: str, **kwargs):
        try:
            await self.websocket.send_json({
                "type": "llm_token",
                "agent": self.agent_name,
                "token": token
            })
        except Exception:
            pass
        
    async def on_llm_end(self, response, **kwargs):
        try:
            await self.websocket.send_json({
                "type": "llm_end",
                "agent": self.agent_name
            })
        except Exception:
            pass

app = FastAPI(title="HarnessFOAM API", description="Web API for HarnessFOAM CFD Agent")

# Define paths
current_dir = os.path.dirname(os.path.abspath(__file__))
web_dir = os.path.join(os.path.dirname(current_dir), "web")

# Ensure web dir exists
os.makedirs(web_dir, exist_ok=True)

class SimulationRequest(BaseModel):
    prompt: str
    output_dir: str = "demo_run_web"

# Mount static files
app.mount("/static", StaticFiles(directory=web_dir), name="static")

@app.get("/")
def read_root():
    return FileResponse(os.path.join(web_dir, "index.html"))

@app.get("/api/browse_folder")
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
        print(f"Error opening folder dialog: {e}")
        
    return {"path": folder_path}

@app.get("/api/models")
def get_models(api_base: str = "", api_key: str = ""):
    """Fetches available models from an OpenAI-compatible /models endpoint."""
    import requests
    
    if not api_base:
        return {"models": [], "error": "API Base URL is required"}
        
    # Standardize the endpoint url
    url = api_base.rstrip("/")
    if not url.endswith("/models"):
        url = url + "/models"
        
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        models = [m.get("id") for m in data.get("data", []) if m.get("id")]
        return {"models": models, "error": None}
    except Exception as e:
        return {"models": [], "error": str(e)}

@app.get("/api/files")
def list_files(path: str = ""):
    """Lists files and directories for a given path."""
    import os
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

@app.get("/api/file_content")
def get_file_content(path: str = ""):
    import os
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

class SaveFileRequest(BaseModel):
    path: str
    content: str

@app.post("/api/save_file")
def save_file(req: SaveFileRequest):
    import os
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

@app.post("/api/delete_file")
def delete_file(req: DeleteRequest):
    import os
    import shutil
    path = req.path
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

@app.post("/api/rename_file")
def rename_file(req: RenameRequest):
    import os
    path = req.path
    new_name = req.new_name
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

@app.post("/api/copy_paste_file")
def copy_paste_file(req: CopyPasteRequest):
    import os
    import shutil
    src = req.src_path
    dest_dir = req.dest_dir
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

@app.post("/api/create_item")
def create_item(req: CreateRequest):
    import os
    parent = req.parent_path
    name = req.name
    is_dir = req.is_dir
    
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

@app.get("/api/cwd")
def get_cwd():
    import os
    return {"cwd": os.getcwd().replace("\\", "/")}

@app.get("/api/system_status")
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
            res = subprocess.run(["wsl", "bash", "-c", "command -v blockMesh"], capture_output=True, text=True, timeout=15)
            if res.returncode == 0 and res.stdout.strip():
                status["openfoam"] = True
                status["method"] = "WSL"
                return status
        except Exception:
            pass
            
    return status

@app.get("/api/llm_status")
def llm_status(api_base: str = "", api_key: str = ""):
    import os
    import requests
    
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
        response = requests.get(url, headers=headers, timeout=5)
        response.raise_for_status()
        return {"status": "ok", "message": "API Responding"}
    except Exception as e:
        return {"status": "error", "message": "Connection Failed"}

# Global variables for tracking active process and websocket task to allow cancelling/stopping them
active_process = None
active_ws_task = None

@app.post("/api/stop")
def stop_execution():
    global active_process, active_ws_task
    stopped = False
    
    # 1. Cancel the active WebSocket task (Generate Files / LangGraph)
    if active_ws_task and not active_ws_task.done():
        try:
            active_ws_task.cancel()
            stopped = True
        except Exception:
            pass
        active_ws_task = None
        
    # 2. Terminate the active solver process (Run OpenFOAM)
    if active_process:
        try:
            active_process.kill()
            stopped = True
        except Exception:
            pass
        active_process = None
        
    # 3. Kill any OpenFOAM solvers in WSL/Linux
    try:
        import subprocess
        import shutil
        if shutil.which("wsl"):
            subprocess.run(["wsl", "killall", "blockMesh", "simpleFoam", "icoFoam", "scalarTransportFoam", "rhoSimpleFoam", "pimpleFoam"], capture_output=True)
        else:
            subprocess.run(["killall", "blockMesh", "simpleFoam", "icoFoam", "scalarTransportFoam", "rhoSimpleFoam", "pimpleFoam"], capture_output=True)
        stopped = True
    except Exception:
        pass
        
    return {"status": "ok", "message": "Stopped successfully." if stopped else "No active process to stop."}

# 2026-08-15 – Gemini 3.5 Flash: Helper to run a command and stream output without using asyncio subprocesses (prevents NotImplementedError on Windows)
async def run_command_and_stream(cmd: list, cwd: str, agent_name: str, websocket: WebSocket):
    import subprocess
    import threading
    import queue
    import asyncio
    import json
    
    q = queue.Queue()
    
    def read_output(proc, q):
        try:
            for line in iter(proc.stdout.readline, ''):
                q.put(line)
        finally:
            proc.stdout.close()
            q.put(None)
            
    try:
        global active_process
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace"
        )
        active_process = proc
        
        t = threading.Thread(target=read_output, args=(proc, q), daemon=True)
        t.start()
        
        loop = asyncio.get_running_loop()
        while True:
            line = await loop.run_in_executor(None, q.get)
            if line is None:
                break
            await websocket.send_text(json.dumps({
                "type": "step",
                "agent": agent_name,
                "message": line.strip()
            }))
            
        await loop.run_in_executor(None, proc.wait)
        return proc.returncode
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e
    finally:
        active_process = None

async def install_openfoam(websocket: WebSocket):
    import json
    import shutil
    
    await websocket.send_text(json.dumps({
        "type": "info",
        "message": "Starting OpenFOAM Auto-Installer..."
    }))
    
    if not shutil.which("wsl"):
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": "WSL is not installed. Please install WSL first."
        }))
        return

    await websocket.send_text(json.dumps({
        "type": "step",
        "agent": "Installer",
        "message": "Updating apt package index in WSL (this may take a moment)..."
    }))
    
    # Run apt-get update
    rc1 = await run_command_and_stream(
        ["wsl", "-u", "root", "apt-get", "update"],
        cwd=None,
        agent_name="Installer",
        websocket=websocket
    )
    
    await websocket.send_text(json.dumps({
        "type": "step",
        "agent": "Installer",
        "message": "Installing openfoam package..."
    }))
    
    # Run apt-get install
    rc2 = await run_command_and_stream(
        ["wsl", "-u", "root", "apt-get", "install", "-y", "openfoam"],
        cwd=None,
        agent_name="Installer",
        websocket=websocket
    )
    
    if rc2 == 0:
        await websocket.send_text(json.dumps({
            "type": "complete",
            "message": "OpenFOAM successfully installed in WSL! Please refresh the page.",
            "directory": "WSL Environment"
        }))
    else:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Installation failed with exit code {rc2}"
        }))

@app.websocket("/api/stream")
async def websocket_endpoint(websocket: WebSocket):
    import json
    import asyncio
    global active_ws_task
    active_ws_task = asyncio.current_task()
    await websocket.accept()
    try:
        # Wait for the client to send the request parameters
        data = await websocket.receive_json()
        
        if data.get("action") == "install":
            await install_openfoam(websocket)
            await websocket.close()
            return
            
        if data.get("action") == "run_openfoam":
            cwd = data.get("output_dir")
            await websocket.send_json({"type": "info", "message": f"Starting OpenFOAM execution in {cwd}..."})
            
            import shutil
            import re
            allrun_path = os.path.join(cwd, "Allrun")
            
            # 2026-08-15 – Gemini 3.5 Flash: Auto-detect and rewrite recursive/corrupted Allrun script
            should_rewrite = not os.path.exists(allrun_path)
            if os.path.exists(allrun_path):
                try:
                    with open(allrun_path, "r", encoding="utf-8", errors="ignore") as f:
                        content = f.read()
                    if "./Allrun" in content or "Local run, no Slurm script needed" in content or "WM_PROJECT_DIR" not in content:
                        should_rewrite = True
                except Exception:
                    should_rewrite = True
                    
            if should_rewrite:
                # Determine solver from controlDict if possible
                solver_name = "icoFoam"
                control_dict_path = os.path.join(cwd, "system", "controlDict")
                if os.path.exists(control_dict_path):
                    try:
                        with open(control_dict_path, "r", encoding="utf-8") as f:
                            c_content = f.read()
                        match = re.search(r"application\s+(\w+);", c_content)
                        if match:
                            solver_name = match.group(1)
                    except Exception:
                        pass
                
                local_script = f"""#!/bin/sh
set -e
# Local execution script generated by HarnessFOAM
# 2026-08-15 – Gemini 3.5 Flash

# Source OpenFOAM environment in WSL/Linux if not already set
if [ -z "$WM_PROJECT_DIR" ]; then
    if [ -f /usr/share/openfoam/etc/bashrc ]; then
        . /usr/share/openfoam/etc/bashrc
    elif [ -f /opt/openfoam*/etc/bashrc ]; then
        . /opt/openfoam*/etc/bashrc
    fi
fi

# Run mesh generation
if [ -f mesh.py ]; then
    echo "Running custom Gmsh python script..."
    python3 mesh.py
    echo "Importing gmsh mesh..."
    gmshToFoam mesh.msh
else
    echo "Running native blockMesh..."
    blockMesh
fi

# Run solver
echo "Running solver {solver_name}..."
{solver_name}
echo "Simulation complete!"
"""
                with open(allrun_path, "w", newline="\n", encoding="utf-8") as f:
                    f.write(local_script)
                try:
                    os.chmod(allrun_path, 0o755)
                except:
                    pass
            
            # 2026-08-15 – Gemini 3.5 Flash: Convert Windows path to WSL path and run with explicit cd
            wsl_cwd = cwd.replace("\\", "/").strip()
            wsl_cwd = re.sub(r"^([a-zA-Z]):", lambda m: f"/mnt/{m.group(1).lower()}", wsl_cwd)
            
            try:
                cmd = ["wsl", "bash", "-c", f"cd '{wsl_cwd}' && bash ./Allrun"] if shutil.which("wsl") else ["sh", "./Allrun"]
                # Cwd is Windows cwd when running under Windows (non-WSL) or wsl.exe wrapper
                run_cwd = cwd if not shutil.which("wsl") else None
                
                rc = await run_command_and_stream(
                    cmd,
                    cwd=run_cwd,
                    agent_name="OpenFOAM",
                    websocket=websocket
                )
                
                if rc == 0:
                    await websocket.send_json({"type": "complete", "message": "Simulation execution completed successfully!"})
                else:
                    await websocket.send_json({"type": "error", "message": f"Simulation execution exited with code {rc}"})
            except Exception as e:
                import traceback
                traceback.print_exc()
                # 2026-08-15 – Gemini 3.5 Flash: Print full repr if str(e) is empty to help diagnose errors
                await websocket.send_json({"type": "error", "message": f"Execution failed: {str(e) or repr(e)}"})
            
            await websocket.close()
            return

        if data.get("action") == "postprocess":
            # 2026-08-15 – Gemini 3.5 Flash: Implement manual post-processing streaming
            cwd = data.get("output_dir")
            await websocket.send_json({"type": "info", "message": f"Starting post-processing execution in {cwd}..."})
            
            import sys
            script_path = os.path.join(cwd, "viz_postprocess.py")
            if not os.path.exists(script_path):
                await websocket.send_json({"type": "error", "message": "viz_postprocess.py not found in output directory. Make sure you run the simulation first."})
                await websocket.close()
                return
                
            case_foam_path = os.path.join(cwd, "case.foam")
            if not os.path.exists(case_foam_path):
                try:
                    with open(case_foam_path, "w") as f:
                        pass
                except Exception as e:
                    print(f"Failed to create case.foam: {e}")
                    
            try:
                with open(script_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if "reader.update()" in content:
                    content = content.replace("reader.update()", "# reader.update()")
                    with open(script_path, "w", encoding="utf-8") as f:
                        f.write(content)
            except Exception as e:
                print(f"Failed to patch reader.update(): {e}")
                
            cmd = [sys.executable, "viz_postprocess.py"]
            rc = await run_command_and_stream(
                cmd,
                cwd=cwd,
                agent_name="Visualizer",
                websocket=websocket
            )
            
            if rc == 0:
                img_path = os.path.join(cwd, "visualization.png")
                img_base64 = ""
                if os.path.exists(img_path):
                    try:
                        import base64
                        with open(img_path, "rb") as image_file:
                            img_base64 = base64.b64encode(image_file.read()).decode('utf-8')
                    except Exception as e:
                        print(f"Failed to read visualization.png: {e}")
                
                payload = {
                    "type": "complete",
                    "message": "Post-processing completed successfully!",
                    "directory": cwd
                }
                if img_base64:
                    payload["image_base64"] = img_base64
                await websocket.send_json(payload)
            else:
                await websocket.send_json({"type": "error", "message": f"Post-processing exited with code {rc}"})
                
            await websocket.close()
            return

        prompt = data.get("prompt", "")
        output_dir = data.get("output_dir", "demo_run_web")
        
        # Parse advanced API settings from the web client
        api_base = data.get("api_base", "").strip()
        model    = data.get("model", "").strip()
        api_key  = data.get("api_key", "").strip()
        post_prompt = data.get("post_prompt", "")
        
        # Build runtime llm_kwargs – these take priority over .env / os.environ
        llm_kwargs: dict = {}
        if api_base: llm_kwargs["base_url"] = api_base
        if model:    llm_kwargs["model"]    = model
        if api_key:  llm_kwargs["api_key"]  = api_key
        llm_kwargs["callbacks"] = [WebSocketStreamingCallbackHandler(websocket, agent_name="Agent")]
        
        await websocket.send_json({"type": "info", "message": f"Initializing workflow for: {prompt}"})
        await websocket.send_json({"type": "step", "agent": "Architect Agent", "message": "Planning file structure and dependencies..."})
        
        workflow = create_workflow()
        initial_state = SimulationState(
            user_requirement=prompt,
            post_prompt=post_prompt,
            case_dir=output_dir,
            llm_kwargs=llm_kwargs
        )
        
        # Execute the actual graph with real-time streaming!
        final_state = initial_state
        async for output in workflow.astream(initial_state):
            for node_name, state in output.items():
                agent_name = node_name.replace("_", " ").title() + " Agent"
                
                # Check for errors in the state logs if any
                if state.get("status") == "FAILED" and node_name == "runner":
                    await websocket.send_json({"type": "step", "agent": agent_name, "message": "Simulation failed, routing to Reviewer..."})
                else:
                    await websocket.send_json({"type": "step", "agent": agent_name, "message": f"Task completed successfully."})
                
                final_state = state
                
                # Predict next node to show progress immediately
                next_agent = None
                if node_name == "architect": next_agent = ("Meshing Agent", "Generating blockMesh/snappyHexMesh topology...")
                elif node_name == "meshing": next_agent = ("Input Writer Agent", "Compiling numerical dictionaries (fvSchemes, fvSolution)...")
                elif node_name == "input_writer": next_agent = ("Runner Agent", "Executing physics solvers locally...")
                elif node_name == "runner": 
                    if state.get("status") == "SUCCESS":
                        next_agent = ("Visualizer Agent", "Running PyVista post-processing pipeline...")
                    else:
                        next_agent = ("Reviewer Agent", "Validating dictionary syntax and physical constraints...")
                elif node_name == "reviewer": next_agent = ("Input Writer Agent", "Re-compiling numerical dictionaries with fixes...")
                
                if next_agent:
                    await websocket.send_json({"type": "step", "agent": next_agent[0], "message": next_agent[1]})
                
        files_created = [f"{f['folder']}/{f['file']}" for f in final_state.get("file_plan", [])]
        
        response_payload = {
            "type": "complete", 
            "message": "Simulation workflow complete!", 
            "directory": output_dir,
            "files": files_created
        }
        
        if final_state.get("image_base64"):
            response_payload["image_base64"] = final_state.get("image_base64")
            
        await websocket.send_json(response_payload)
        
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        # 2026-08-15 – Gemini 3.5 Flash: Remove redundant global declaration to fix SyntaxError
        if active_ws_task == asyncio.current_task():
            active_ws_task = None

@app.websocket("/api/chat_stream")
async def chat_websocket_endpoint(websocket: WebSocket):
    import json
    import os
    from harnessfoam.agents.llm_config import build_llm
    from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

    await websocket.accept()
    
    # Maintain chat history per session
    history = [
        SystemMessage(content="""You are HarnessFOAM Assistant, an expert AI prompt engineer and OpenFOAM simulation specialist.
Your job is to help users optimize their simulation prompts and guide them on how to use this web application.
Keep your answers helpful, concise, and focused on OpenFOAM setups or prompt engineering for CFD.
""")
    ]

    try:
        while True:
            data = await websocket.receive_json()
            user_msg = data.get("message", "")
            current_prompt = data.get("current_prompt", "")
            post_prompt = data.get("post_prompt", "")
            output_dir = data.get("output_dir", "")
            openfoam_status = data.get("openfoam_status", "")
            
            # 2026-08-15 – Claude Opus 4.6: pass kwargs directly instead of
            # mutating os.environ (avoids race conditions and ensures
            # the model set in Settings is always used by the LLM)
            api_base = data.get("api_base", "").strip()
            model = data.get("model", "").strip()
            api_key = data.get("api_key", "").strip()
            
            if not user_msg: continue
            
            llm_kwargs: dict = {}
            if api_base: llm_kwargs["base_url"] = api_base
            if model:    llm_kwargs["model"]    = model
            if api_key:  llm_kwargs["api_key"]  = api_key
            
            llm = build_llm(temperature=0.7, **llm_kwargs)
            
            # Inject context
            context_msg = f"""[System Context - User's Current Settings]
Simulation Requirement: {current_prompt}
Post-Processing Requirement: {post_prompt}
Output Directory: {output_dir}
OpenFOAM Status: {openfoam_status}

User Question:
{user_msg}"""
            history.append(HumanMessage(content=context_msg))
            
            full_reply = ""
            async for chunk in llm.astream(history):
                content = chunk.content
                if content:
                    full_reply += content
                    await websocket.send_json({"type": "chunk", "text": content})
                    
            # Approximate token calculation
            total_prompt_chars = sum(len(m.content) for m in history)
            total_reply_chars = len(full_reply)
            prompt_tokens = max(1, total_prompt_chars // 4)
            completion_tokens = max(1, total_reply_chars // 4)
            
            await websocket.send_json({"type": "usage", "prompt": prompt_tokens, "completion": completion_tokens})
            
            history.append(AIMessage(content=full_reply))
            await websocket.send_json({"type": "done"})
            
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "text": str(e)})

def start_server(host="127.0.0.1", port=8000):
    print(f"Starting HarnessFOAM Web Interface at http://{host}:{port}")
    # 2026-08-15 – Gemini 3.5 Flash: Enable auto-reload for future development convenience
    uvicorn.run("harnessfoam.api.server:app", host=host, port=port, reload=True)
