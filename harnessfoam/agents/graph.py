from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
import time

class SimulationState(TypedDict, total=False):
    prompt: str
    post_prompt: str
    user_requirement: str
    case_id: str
    case_dir: str
    plan: List[Dict[str, str]]
    file_plan: List[Dict[str, str]]
    mesh_job_id: Optional[str]
    run_job_id: Optional[str]
    viz_job_id: Optional[str]
    status: str
    logs: Dict[str, Any]
    errors: int
    max_errors: int
    current_step: str
    image_base64: Optional[str]
    llm_kwargs: Optional[Dict[str, Any]]  # Runtime API overrides passed from server

from harnessfoam.agents.architect import plan_simulation

def architect_node(state: SimulationState) -> SimulationState:
    # Normalize state for backward compatibility
    if 'prompt' not in state and 'user_requirement' in state:
        state['prompt'] = state['user_requirement']
    if 'case_id' not in state and 'case_dir' in state:
        state['case_id'] = state['case_dir']
    if 'case_dir' not in state and 'case_id' in state:
        state['case_dir'] = state['case_id']
    
    if state.get('case_dir') and state['case_dir'].startswith('demo_') and not state['case_dir'].startswith('demo/'):
        state['case_dir'] = f"demo/{state['case_dir']}"
    if 'logs' not in state:
        state['logs'] = {}
    if 'errors' not in state:
        state['errors'] = 0
    if 'max_errors' not in state:
        state['max_errors'] = 3
    if 'status' not in state:
        state['status'] = 'PENDING'
    state['current_step'] = 'architect'

    print(f"Architect Agent: Planning simulation for case {state['case_id']}")
    llm_kwargs = state.get('llm_kwargs') or {}
    state['plan'] = plan_simulation(state['prompt'], llm_kwargs=llm_kwargs)
    state['file_plan'] = state['plan']
    print(f"Architect plan generated: {len(state['plan'])} files.")
    return state

from harnessfoam.agents.meshing import generate_mesh_script
from harnessfoam.agents.visualizer import generate_visualization_script

def meshing_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'meshing'
    print(f"Meshing Agent: Generating mesh for case {state['case_id']}")
    
    llm_kwargs = state.get('llm_kwargs') or {}
    mesh_results = generate_mesh_script(state['prompt'], llm_kwargs=llm_kwargs)
    state['logs']['is_gmsh_required'] = mesh_results['is_gmsh_required']
    state['logs']['mesh_python_script'] = mesh_results['python_script']
    
    # 2026-08-15 – Gemini 3.5 Flash: Write mesh.py if gmsh is required
    if mesh_results['is_gmsh_required'] and mesh_results['python_script']:
        import os
        case_dir = state.get('case_dir')
        if case_dir:
            os.makedirs(case_dir, exist_ok=True)
            mesh_script_path = os.path.join(case_dir, "mesh.py")
            with open(mesh_script_path, "w", newline="\n", encoding="utf-8") as f:
                f.write(mesh_results['python_script'])
            print(f"Meshing Agent: Wrote gmsh script to {mesh_script_path}")
            
    state['mesh_job_id'] = f"mesh_{state['case_id']}_{int(time.time())}"
    return state

from harnessfoam.agents.input_writer import write_simulation_inputs

def input_writer_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'input_writer'
    print(f"Input Writer Agent: Generating files for {len(state['plan'])} configurations")
    llm_kwargs = state.get('llm_kwargs') or {}
    state['logs']['generated_files'] = write_simulation_inputs(state['plan'], state['prompt'], llm_kwargs=llm_kwargs)
    
    # Write files to disk
    import os
    case_dir = state.get('case_dir')
    if case_dir:
        os.makedirs(case_dir, exist_ok=True)
        for rel_path, content in state['logs']['generated_files'].items():
            safe_rel_path = rel_path.lstrip("/\\")
            full_path = os.path.join(case_dir, safe_rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            # 2026-08-15 – Gemini 3.5 Flash: write with LF endings to prevent WSL errors
            with open(full_path, "w", newline="\n", encoding="utf-8") as f:
                f.write(content)
                
    state['file_plan'] = state['plan']
    return state

from harnessfoam.agents.runner import generate_hpc_script, execute_simulation
from harnessfoam.agents.reviewer import analyze_errors

def runner_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'runner'
    print(f"Runner Agent: Generating run script...")
    state['run_job_id'] = f"run_{state['case_id']}_{int(time.time())}"
    
    llm_kwargs = state.get('llm_kwargs') or {}
    slurm_script = generate_hpc_script(state['prompt'], llm_kwargs=llm_kwargs)
    state['logs']['slurm_script'] = slurm_script
    
    # 2026-08-15 – Gemini 3.5 Flash: Avoid recursive execution loop on local run
    import os
    import re
    allrun_path = os.path.join(state['case_dir'], "Allrun")
    
    is_hpc = any(x in state['prompt'].lower() for x in ["hpc", "slurm", "cluster"])
    
    if not is_hpc:
        # Determine solver from controlDict if possible
        solver_name = "icoFoam"
        control_dict_path = os.path.join(state['case_dir'], "system", "controlDict")
        if os.path.exists(control_dict_path):
            try:
                with open(control_dict_path, "r", encoding="utf-8") as f:
                    content = f.read()
                match = re.search(r"application\s+(\w+);", content)
                if match:
                    solver_name = match.group(1)
            except Exception:
                pass
                
        local_script = f"""#!/bin/sh
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
    else:
        with open(allrun_path, "w", newline="\n", encoding="utf-8") as f:
            f.write(slurm_script)
    
    # Make it executable (cross-platform fallback)
    try:
        os.chmod(allrun_path, 0o755)
    except: pass
    
    state['status'] = 'SUCCESS'
    return state

def reviewer_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'reviewer'
    print(f"Reviewer Agent: Analyzing errors...")
    state['errors'] += 1
    
    error_logs = state['logs'].get('execution_error', 'Unknown error')
    llm_kwargs = state.get('llm_kwargs') or {}
    review_results = analyze_errors(error_logs, llm_kwargs=llm_kwargs)
    state['logs']['review_suggestions'] = review_results['suggestions']
    print(f"Reviewer found {len(review_results['suggestions'])} fixes to apply.")
    return state

from harnessfoam.agents.visualizer import execute_visualization

def visualizer_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'visualizer'
    print(f"Visualization Agent: Generating visuals...")
    
    # If the user provided a custom post-processing prompt, use it; else use the main prompt
    viz_prompt = state.get('post_prompt') or state.get('prompt')
    
    llm_kwargs = state.get('llm_kwargs') or {}
    viz_results = generate_visualization_script(viz_prompt, llm_kwargs=llm_kwargs)
    state['logs']['is_visualization_required'] = viz_results['is_visualization_required']
    state['logs']['pyvista_script'] = viz_results['pyvista_script']
    
    if viz_results['is_visualization_required'] and state['status'] == 'SUCCESS':
        print("Visualizer Agent generated PyVista script. Executing locally...")
        img_base64 = execute_visualization(state['case_dir'], viz_results['pyvista_script'])
        if img_base64:
            state['image_base64'] = img_base64
            print("Visualization successfully rendered.")
    else:
        print("No visualization requested or simulation failed.")
        
    state['viz_job_id'] = f"viz_{state['case_id']}_{int(time.time())}"
    return state

def end_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'end'
    return state

def should_review(state: SimulationState) -> str:
    if state['status'] == 'FAILED' and state['errors'] < state['max_errors']:
        return "review"
    elif state['status'] == 'FAILED':
        return "fail"
    return "visualize"

def create_workflow() -> StateGraph:
    workflow = StateGraph(SimulationState)
    
    workflow.add_node("architect", architect_node)
    workflow.add_node("meshing", meshing_node)
    workflow.add_node("input_writer", input_writer_node)
    workflow.add_node("runner", runner_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("visualizer", visualizer_node)
    workflow.add_node("end", end_node)
    
    workflow.set_entry_point("architect")
    workflow.add_edge("architect", "meshing")
    workflow.add_edge("meshing", "input_writer")
    workflow.add_edge("input_writer", "runner")
    
    workflow.add_conditional_edges(
        "runner",
        should_review,
        {
            "review": "reviewer",
            "visualize": "visualizer",
            "fail": "end"
        }
    )
    workflow.add_edge("reviewer", "input_writer") # Reviewer fixes and resubmits
    workflow.add_edge("visualizer", "end")
    workflow.add_edge("end", END)
    
    return workflow.compile()
