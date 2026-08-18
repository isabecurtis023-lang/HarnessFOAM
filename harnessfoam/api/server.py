import os
import asyncio
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import uvicorn
from harnessfoam.agents.graph import create_workflow, SimulationState
from langchain_core.callbacks import BaseCallbackHandler
import logging
logger = logging.getLogger(__name__)


class WebSocketStreamingCallbackHandler(BaseCallbackHandler):
    def __init__(self, websocket: WebSocket, agent_name: str = "LLM"):
        self.websocket = websocket
        self.agent_name = agent_name
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            self.loop = asyncio.get_event_loop()
        self.usage = {}

    def on_chat_model_start(self, serialized: dict, messages: list, **kwargs):
        # Extract prompt from messages
        prompt_text = "\n".join([m.content for m in messages[0]]) if messages and messages[0] else ""
        try:
            asyncio.run_coroutine_threadsafe(
                self.websocket.send_json({
                    "type": "llm_start",
                    "agent": self.agent_name,
                    "prompt": prompt_text
                }),
                self.loop
            )
        except Exception:
            pass

    def on_llm_new_token(self, token: str, **kwargs):
        logger.debug("TOKEN: %r", token)
        try:
            asyncio.run_coroutine_threadsafe(
                self.websocket.send_json({
                    "type": "llm_token",
                    "agent": self.agent_name,
                    "token": token
                }),
                self.loop
            )
        except Exception:
            pass
        
    def on_llm_end(self, response, **kwargs):
        try:
            metadata = getattr(response, "llm_output", None) or getattr(response, "response_metadata", None) or {}
            usage = metadata.get("token_usage") or metadata.get("usage") or {}
            self.usage = {
                "prompt_tokens": usage.get("prompt_tokens", usage.get("input_tokens")),
                "completion_tokens": usage.get("completion_tokens", usage.get("output_tokens")),
            }
        except Exception:
            self.usage = {}
        try:
            asyncio.run_coroutine_threadsafe(
                self.websocket.send_json({
                    "type": "llm_end",
                    "agent": self.agent_name
                }),
                self.loop
            )
        except Exception:
            pass

app = FastAPI(title="HarnessFOAM API", description="Web API for HarnessFOAM CFD Agent")

# Define paths
current_dir = os.path.dirname(os.path.abspath(__file__))
web_dir = os.path.join(os.path.dirname(current_dir), "web")

# Ensure web dir exists
os.makedirs(web_dir, exist_ok=True)


from harnessfoam.api.routes import router as api_router

# Mount static files
current_dir = os.path.dirname(os.path.abspath(__file__))
web_dir = os.path.join(os.path.dirname(current_dir), "web")
app.mount("/static", StaticFiles(directory=web_dir), name="static")
assets_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "assets")
if os.path.isdir(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

app.include_router(api_router)

from harnessfoam.core.job_manager import job_manager

@app.post("/api/stop")
def stop_execution():
    stopped = False
    
    # 1. Terminate all active processes/tasks in the job manager
    for key, task_or_proc in list(job_manager.tasks.items()):
        try:
            if hasattr(task_or_proc, "kill"):
                task_or_proc.kill()
            elif hasattr(task_or_proc, "cancel"):
                task_or_proc.cancel()
            stopped = True
        except Exception:
            pass
        del job_manager.tasks[key]
        
    # 2. Kill any OpenFOAM solvers in WSL/Linux
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

async def run_command_and_stream(cmd: list, cwd: str, agent_name: str, websocket: WebSocket, env: dict = None):
    import asyncio
    import json
    
    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=cwd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            env=env
        )
        
        job_manager.tasks[str(id(websocket))] = proc
        
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            await websocket.send_text(json.dumps({
                "type": "openfoam_log" if agent_name == "OpenFOAM" else "step",
                "agent": agent_name,
                "message": line.decode('utf-8', errors='replace').strip(),
                "is_error": False
            }))
            
        await proc.wait()
        return proc.returncode
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise e
    finally:
        if str(id(websocket)) in job_manager.tasks:
            del job_manager.tasks[str(id(websocket))]
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
                if [ -f /opt/openfoam13/etc/bashrc ]; then
                    . /opt/openfoam13/etc/bashrc
                else
                    for foamrc in /opt/openfoam*/etc/bashrc; do
                        if [ -f "$foamrc" ]; then . "$foamrc"; break; fi
                    done
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

echo "Checking mesh quality..."
checkMesh

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
            post_prompt = data.get("post_prompt", "")
            
            # Extract advanced API settings
            api_base = data.get("api_base", "").strip()
            model    = data.get("model", "").strip()
            api_key  = data.get("api_key", "").strip()
            llm_kwargs = {}
            if api_base: llm_kwargs["base_url"] = api_base
            if model:    llm_kwargs["model"]    = model
            if api_key:  llm_kwargs["api_key"]  = api_key
            llm_kwargs["callbacks"] = [WebSocketStreamingCallbackHandler(websocket, agent_name="Visualizer Agent")]

            await websocket.send_json({"type": "info", "message": f"Starting post-processing execution in {cwd}..."})
            await websocket.send_json({"type": "step", "agent": "Visualizer Agent", "message": "Analyzing prompt and generating PyVista script..."})
            
            from harnessfoam.agents.visualizer import generate_visualization_script
            
            import asyncio
            import functools
            loop = asyncio.get_running_loop()
            func = functools.partial(generate_visualization_script, post_prompt or "Visualize the flow field", llm_kwargs=llm_kwargs)
            # Run in executor so it doesn't block the async event loop, allowing websocket tokens to stream
            viz_results = await loop.run_in_executor(None, func)
            
            await websocket.send_json({"type": "step", "agent": "Visualizer Agent", "message": "LLM generation finished. Writing PyVista script..."})
            
            pyvista_script = viz_results.get('pyvista_script', '')
            
            import sys
            script_path = os.path.join(cwd, "viz_postprocess.py")
            if not pyvista_script:
                await websocket.send_json({"type": "error", "message": "Visualizer Agent failed to generate a script."})
                await websocket.close()
                return
                
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(pyvista_script)
                
            case_foam_path = os.path.join(cwd, "case.foam")
            if not os.path.exists(case_foam_path):
                try:
                    with open(case_foam_path, "w") as f:
                        pass
                except Exception as e:
                    logger.info(f"Failed to create case.foam: {e}")
                    
            try:
                with open(script_path, "r", encoding="utf-8") as f:
                    content = f.read()
                if "reader.update()" in content:
                    content = content.replace("reader.update()", "# reader.update()")
                    with open(script_path, "w", encoding="utf-8") as f:
                        f.write(content)
            except Exception as e:
                logger.info(f"Failed to patch reader.update(): {e}")
                
            import shutil
            cmd = [sys.executable, "viz_postprocess.py"]
            if shutil.which("xvfb-run") and os.name == "posix":
                cmd = ["xvfb-run", "-a"] + cmd
                
            # Force off_screen via env var to prevent any VTK message boxes from hanging the script
            env = os.environ.copy()
            env["PYVISTA_OFF_SCREEN"] = "true"
            env["VTK_DISABLE_VIS_TEST"] = "1"
            
            rc = await run_command_and_stream(
                cmd,
                cwd=cwd,
                agent_name="Visualizer",
                websocket=websocket,
                env=env
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
                        logger.info(f"Failed to read visualization.png: {e}")
                
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
        max_loops = int(data.get("max_loops", 3))
        memory_enabled = bool(data.get("memory_enabled", False))
        memory_limits = data.get("memory_limits") or {}
        
        # Build runtime llm_kwargs – these take priority over .env / os.environ
        llm_kwargs: dict = {}
        if api_base: llm_kwargs["base_url"] = api_base
        if model:    llm_kwargs["model"]    = model
        if api_key:  llm_kwargs["api_key"]  = api_key
        llm_kwargs["callbacks"] = [WebSocketStreamingCallbackHandler(websocket, agent_name="Agent")]
        
        await websocket.send_json({"type": "info", "message": f"Initializing workflow for: {prompt}"})
        await websocket.send_json({"type": "info", "message": "<br>--- Starting Initial Run ---"})
        await websocket.send_json({"type": "step", "agent": "Architect Agent", "message": "Planning file structure and dependencies..."})
        
        workflow = create_workflow()
        initial_state = SimulationState(
            user_requirement=prompt,
            post_prompt=post_prompt,
            case_dir=output_dir,
            llm_kwargs=llm_kwargs,
            max_errors=max_loops,
            memory_enabled=memory_enabled,
            memory_limits=memory_limits,
            # Deep Driving includes the visualizer stage automatically.
            auto_postprocess=True
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
                
                if node_name == "reviewer":
                    loop_idx = state.get("errors", 1)
                    await websocket.send_json({"type": "info", "message": f"<br>--- Starting Error Recovery Loop {loop_idx} ---"})
                
                final_state = state
                
                # Predict next node to show progress immediately
                next_agent = None
                if node_name == "architect": next_agent = ("Meshing Agent", "Generating blockMesh/snappyHexMesh topology...")
                elif node_name == "meshing": next_agent = ("Input Writer Agent", "Compiling numerical dictionaries (fvSchemes, fvSolution)...")
                elif node_name == "input_writer": next_agent = ("Preflight Validator", "Checking dictionary consistency before solver launch...")
                elif node_name == "preflight":
                    if state.get("status") == "FAILED":
                        next_agent = ("Reviewer Agent", "Diagnosing preflight validation failures...")
                    else:
                        next_agent = ("Runner Agent", "Executing physics solvers locally...")
                elif node_name == "runner": 
                    if state.get("status") == "SUCCESS":
                        next_agent = ("Visualizer Agent", "Running PyVista post-processing pipeline...")
                    else:
                        next_agent = ("Reviewer Agent", "Validating dictionary syntax and physical constraints...")
                elif node_name == "reviewer": 
                    suggestions = state.get('logs', {}).get('review_suggestions', [])
                    if any(s.get('file') == 'mesh.py' for s in suggestions):
                        next_agent = ("Meshing Agent", "Re-generating mesh script with Reviewer feedback...")
                    else:
                        next_agent = ("Input Writer Agent", "Re-compiling numerical dictionaries with fixes...")
                
                if next_agent:
                    await websocket.send_json({"type": "step", "agent": next_agent[0], "message": next_agent[1]})
                
        files_created = [f"{f['folder']}/{f['file']}" for f in final_state.get("file_plan", [])]
        
        response_payload = {
            "type": "complete", 
            "message": "Simulation workflow complete!", 
            "directory": output_dir,
            "files": files_created
        }

        response_payload["postprocess_status"] = final_state.get("logs", {}).get("postprocess_status", "SKIPPED")
        response_payload["preflight_ok"] = final_state.get("logs", {}).get("preflight_ok")
        response_payload["runtime_metrics"] = final_state.get("logs", {}).get("runtime_metrics", {})
        response_payload["physics_metrics"] = final_state.get("logs", {}).get("physics_metrics", {})
        response_payload["benchmark_metrics"] = final_state.get("logs", {}).get("benchmark_metrics", {})
        response_payload["postprocess_metrics"] = final_state.get("logs", {}).get("postprocess_metrics", {})
        response_payload["visual_review"] = final_state.get("logs", {}).get("visual_review", {})
        response_payload["failure_ledger"] = final_state.get("logs", {}).get("failure_ledger_summary", {})
        response_payload["retry_history"] = final_state.get("retry_history", [])
        from harnessfoam.telemetry import estimate_cost
        callback_usage = {}
        for callback in llm_kwargs.get("callbacks", []):
            callback_usage = getattr(callback, "usage", {}) or {}
            if callback_usage:
                break
        response_payload["llm_usage"] = estimate_cost(callback_usage, llm_kwargs.get("model", ""))
        
        if final_state.get("image_base64"):
            response_payload["image_base64"] = final_state.get("image_base64")
            
        await websocket.send_json(response_payload)
        
    except WebSocketDisconnect:
        logger.info("Client disconnected")
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

            from harnessfoam.assistant_tools import assistant_command
            tool_result = assistant_command(user_msg, output_dir=output_dir or "tmp_assistant_cavity")
            if tool_result:
                await websocket.send_json({"type": "tool_result", "tool": tool_result["tool"], "result": tool_result["result"]})
                await websocket.send_json({"type": "chunk", "text": json.dumps(tool_result["result"], ensure_ascii=False, indent=2)})
                await websocket.send_json({"type": "usage", "prompt": 0, "completion": 0})
                await websocket.send_json({"type": "done"})
                continue
            
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
    logger.info(f"Starting HarnessFOAM Web Interface at http://{host}:{port}")
    # 2026-08-15 – Gemini 3.5 Flash: Enable auto-reload for future development convenience
    uvicorn.run("harnessfoam.api.server:app", host=host, port=port, reload=True)
