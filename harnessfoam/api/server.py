import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
from harnessfoam.agents.graph import create_workflow, SimulationState

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

async def install_openfoam(websocket: WebSocket):
    import subprocess
    import shutil
    import json
    
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
    process1 = await asyncio.create_subprocess_exec(
        "wsl", "-u", "root", "apt-get", "update",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    
    while True:
        line = await process1.stdout.readline()
        if not line:
            break
        await websocket.send_text(json.dumps({
            "type": "step",
            "agent": "Installer",
            "message": line.decode('utf-8', errors='replace').strip()
        }))
    await process1.wait()
    
    await websocket.send_text(json.dumps({
        "type": "step",
        "agent": "Installer",
        "message": "Installing openfoam package..."
    }))
    
    # Run apt-get install
    process2 = await asyncio.create_subprocess_exec(
        "wsl", "-u", "root", "apt-get", "install", "-y", "openfoam",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT
    )
    
    while True:
        line = await process2.stdout.readline()
        if not line:
            break
        await websocket.send_text(json.dumps({
            "type": "step",
            "agent": "Installer",
            "message": line.decode('utf-8', errors='replace').strip()
        }))
    await process2.wait()
    
    if process2.returncode == 0:
        await websocket.send_text(json.dumps({
            "type": "complete",
            "message": "OpenFOAM successfully installed in WSL! Please refresh the page.",
            "directory": "WSL Environment"
        }))
    else:
        await websocket.send_text(json.dumps({
            "type": "error",
            "message": f"Installation failed with exit code {process2.returncode}"
        }))

@app.websocket("/api/stream")
async def websocket_endpoint(websocket: WebSocket):
    import json
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
                    if "./Allrun" in content or "Local run, no Slurm script needed" in content:
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
# Local execution script generated by HarnessFOAM
# 2026-08-15 – Gemini 3.5 Flash

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
            
            try:
                if shutil.which("wsl"):
                    process = await asyncio.create_subprocess_exec(
                        "wsl", "bash", "./Allrun",
                        cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
                    )
                else:
                    process = await asyncio.create_subprocess_exec(
                        "sh", "./Allrun",
                        cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
                    )
                while True:
                    line = await process.stdout.readline()
                    if not line: break
                    await websocket.send_json({"type": "step", "agent": "OpenFOAM", "message": line.decode('utf-8', errors='replace').strip()})
                await process.wait()
                await websocket.send_json({"type": "complete", "message": "Simulation execution completed!"})
            except Exception as e:
                await websocket.send_json({"type": "error", "message": f"Execution failed: {str(e)}"})
            
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
    uvicorn.run("harnessfoam.api.server:app", host=host, port=port, reload=False)
