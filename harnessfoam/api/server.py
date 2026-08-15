# 2026-08-15 (gemini-2.5-pro)
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

@app.websocket("/api/stream")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        # Wait for the client to send the simulation request parameters
        data = await websocket.receive_json()
        prompt = data.get("prompt", "")
        output_dir = data.get("output_dir", "demo_run_web")
        
        # Parse advanced API settings
        api_base = data.get("api_base")
        model = data.get("model")
        api_key = data.get("api_key")
        
        if api_base: os.environ["OPENAI_API_BASE"] = api_base
        if model: os.environ["LLM_MODEL"] = model
        if api_key: os.environ["OPENAI_API_KEY"] = api_key
        
        await websocket.send_json({"type": "info", "message": f"Initializing workflow for: {prompt}"})
        
        workflow = create_workflow()
        initial_state = SimulationState(
            user_requirement=prompt,
            case_dir=output_dir
        )
        
        # In a real async streaming setup with LangGraph, we would use workflow.astream()
        # For demonstration of the UI, we simulate the agent processing steps before blocking on ainvoke
        steps = [
            ("Architect Agent", "Planning file structure and dependencies..."),
            ("Meshing Agent", "Generating blockMesh/snappyHexMesh topology..."),
            ("Input Writer Agent", "Compiling numerical dictionaries (fvSchemes, fvSolution)..."),
            ("Reviewer Agent", "Validating dictionary syntax and physical constraints..."),
            ("Runner Agent", "Preparing HPC SLURM scripts and solver commands...")
        ]
        
        for agent, action in steps:
            await asyncio.sleep(1.5)
            await websocket.send_json({"type": "step", "agent": agent, "message": action})
            
        await websocket.send_json({"type": "info", "message": "Executing full graph in background..."})
        
        # Execute the actual graph
        final_state = await workflow.ainvoke(initial_state)
        
        files_created = [f"{f['folder']}/{f['file']}" for f in final_state.get("file_plan", [])]
        
        await websocket.send_json({
            "type": "complete", 
            "message": "Simulation workflow complete!", 
            "directory": output_dir,
            "files": files_created
        })
        
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})

def start_server(host="127.0.0.1", port=8000):
    print(f"Starting HarnessFOAM Web Interface at http://{host}:{port}")
    uvicorn.run("harnessfoam.api.server:app", host=host, port=port, reload=False)
