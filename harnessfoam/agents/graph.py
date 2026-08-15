from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
import time

# 2026-08-15 | Gemini 3.5 Flash (Medium)
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

from harnessfoam.agents.architect import plan_simulation

# 2026-08-15 | Gemini 3.5 Flash (Low)
def architect_node(state: SimulationState) -> SimulationState:
    # Normalize state for backward compatibility
    if 'prompt' not in state and 'user_requirement' in state:
        state['prompt'] = state['user_requirement']
    if 'case_id' not in state and 'case_dir' in state:
        state['case_id'] = state['case_dir']
    if 'case_dir' not in state and 'case_id' in state:
        state['case_dir'] = state['case_id']
    
    # 2026-08-15 | Gemini 3.5 Flash (Low)
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
    state['plan'] = plan_simulation(state['prompt'])
    state['file_plan'] = state['plan']
    print(f"Architect plan generated: {len(state['plan'])} files.")
    return state

from harnessfoam.agents.meshing import generate_mesh_script
from harnessfoam.agents.visualizer import generate_visualization_script

# 2026-08-15 | Gemini 3.5 Flash (Medium)
def meshing_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'meshing'
    print(f"Meshing Agent: Generating mesh for case {state['case_id']}")
    
    mesh_results = generate_mesh_script(state['prompt'])
    state['logs']['is_gmsh_required'] = mesh_results['is_gmsh_required']
    state['logs']['mesh_python_script'] = mesh_results['python_script']
    state['mesh_job_id'] = f"mesh_{state['case_id']}_{int(time.time())}"
    return state

from harnessfoam.agents.input_writer import write_simulation_inputs

# 2026-08-15 | Gemini 3.5 Flash (Low)
def input_writer_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'input_writer'
    print(f"Input Writer Agent: Generating files for {len(state['plan'])} configurations")
    state['logs']['generated_files'] = write_simulation_inputs(state['plan'], state['prompt'])
    
    # Write files to disk
    import os
    case_dir = state.get('case_dir')
    if case_dir:
        os.makedirs(case_dir, exist_ok=True)
        for rel_path, content in state['logs']['generated_files'].items():
            full_path = os.path.join(case_dir, rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, "w") as f:
                f.write(content)
                
    state['file_plan'] = state['plan']
    return state

from harnessfoam.agents.runner import generate_hpc_script, execute_simulation
from harnessfoam.agents.reviewer import analyze_errors

# 2026-08-15 | Gemini 3.5 Flash (Medium)
def runner_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'runner'
    print(f"Runner Agent: Generating run script...")
    state['run_job_id'] = f"run_{state['case_id']}_{int(time.time())}"
    
    slurm_script = generate_hpc_script(state['prompt'])
    state['logs']['slurm_script'] = slurm_script
    
    # Actually execute it locally!
    success, output = execute_simulation(state['case_dir'])
    state['status'] = 'SUCCESS' if success else 'FAILED'
    
    if not success:
        state['logs']['execution_error'] = output
    else:
        state['logs']['execution_output'] = output
        
    return state

# 2026-08-15 | Gemini 3.5 Flash (Medium)
def reviewer_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'reviewer'
    print(f"Reviewer Agent: Analyzing errors...")
    state['errors'] += 1
    
    error_logs = state['logs'].get('execution_error', 'Unknown error')
    review_results = analyze_errors(error_logs)
    state['logs']['review_suggestions'] = review_results['suggestions']
    print(f"Reviewer found {len(review_results['suggestions'])} fixes to apply.")
    return state

from harnessfoam.agents.visualizer import execute_visualization

# 2026-08-15 | Gemini 3.5 Flash (Medium)
def visualizer_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'visualizer'
    print(f"Visualization Agent: Generating visuals...")
    
    # If the user provided a custom post-processing prompt, use it; else use the main prompt
    viz_prompt = state.get('post_prompt') or state.get('prompt')
    
    viz_results = generate_visualization_script(viz_prompt)
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

# 2026-08-15 | Gemini 3.5 Flash (Low)
def end_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'end'
    return state

# 2026-08-15 | Gemini 3.5 Flash (Low)
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
