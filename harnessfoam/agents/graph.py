from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
import time

# 2026-08-15 | Gemini 3.5 Flash (Medium)
class SimulationState(TypedDict, total=False):
    prompt: str
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

from harnessfoam.agents.architect import plan_simulation

# 2026-08-15 | Gemini 3.5 Flash (Medium)
def architect_node(state: SimulationState) -> SimulationState:
    # Normalize state for backward compatibility
    if 'prompt' not in state and 'user_requirement' in state:
        state['prompt'] = state['user_requirement']
    if 'case_id' not in state and 'case_dir' in state:
        state['case_id'] = state['case_dir']
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
    # Call the real LangChain logic
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
    
    # Call real LangChain logic for meshing
    mesh_results = generate_mesh_script(state['prompt'])
    state['logs']['is_gmsh_required'] = mesh_results['is_gmsh_required']
    state['logs']['mesh_python_script'] = mesh_results['python_script']
    if mesh_results['is_gmsh_required']:
        print("Meshing Agent generated Gmsh Python script.")
    else:
        print("Meshing Agent determined native OpenFOAM meshing is sufficient.")
        
    state['mesh_job_id'] = f"mesh_{state['case_id']}_{int(time.time())}"
    return state

from harnessfoam.agents.input_writer import write_simulation_inputs

# 2026-08-15 | Gemini 3.5 Flash (Medium)
def input_writer_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'input_writer'
    print(f"Input Writer Agent: Generating files for {len(state['plan'])} configurations")
    # Call the real LangChain logic
    state['logs']['generated_files'] = write_simulation_inputs(state['plan'], state['prompt'])
    state['file_plan'] = state['plan']
    print(f"Input Writer successfully generated contents for {len(state['logs']['generated_files'])} files.")
    return state

from harnessfoam.agents.runner import generate_hpc_script
from harnessfoam.agents.reviewer import analyze_errors

# 2026-08-15 | Gemini 3.5 Flash (Medium)
def runner_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'runner'
    print(f"Runner Agent: Submitting simulation job...")
    state['run_job_id'] = f"run_{state['case_id']}_{int(time.time())}"
    
    # Generate Slurm script if HPC is requested
    slurm_script = generate_hpc_script(state['prompt'])
    state['logs']['slurm_script'] = slurm_script
    print(f"Runner generated execution script:\n{slurm_script[:50]}...")
    
    # Mocking success or failure
    state['status'] = 'FAILED' if state['errors'] < 1 else 'SUCCESS'
    if state['status'] == 'FAILED':
        state['logs']['execution_error'] = "--> FOAM FATAL ERROR:\nCourant number exceeded 1.0"
    return state

# 2026-08-15 | Gemini 3.5 Flash (Medium)
def reviewer_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'reviewer'
    print(f"Reviewer Agent: Analyzing errors...")
    state['errors'] += 1
    
    # Call the real LangChain logic
    error_logs = state['logs'].get('execution_error', 'Unknown error')
    review_results = analyze_errors(error_logs)
    state['logs']['review_suggestions'] = review_results['suggestions']
    print(f"Reviewer found {len(review_results['suggestions'])} fixes to apply.")
    return state

# 2026-08-15 | Gemini 3.5 Flash (Medium)
def visualizer_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'visualizer'
    print(f"Visualization Agent: Generating visuals...")
    
    # Call real LangChain logic for visualization
    viz_results = generate_visualization_script(state['prompt'])
    state['logs']['is_visualization_required'] = viz_results['is_visualization_required']
    state['logs']['pyvista_script'] = viz_results['pyvista_script']
    if viz_results['is_visualization_required']:
        print("Visualizer Agent generated PyVista script.")
    else:
        print("No visualization requested.")
        
    state['viz_job_id'] = f"viz_{state['case_id']}_{int(time.time())}"
    return state

# 2026-08-15 | Gemini 3.5 Flash (Medium)
def should_review(state: SimulationState) -> str:
    if state['status'] == 'FAILED' and state['errors'] < state['max_errors']:
        return "review"
    elif state['status'] == 'FAILED':
        state['current_step'] = 'end'
        return "fail"
    state['current_step'] = 'end'
    return "visualize"

def create_workflow() -> StateGraph:
    workflow = StateGraph(SimulationState)
    
    workflow.add_node("architect", architect_node)
    workflow.add_node("meshing", meshing_node)
    workflow.add_node("input_writer", input_writer_node)
    workflow.add_node("runner", runner_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("visualizer", visualizer_node)
    
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
            "fail": END
        }
    )
    workflow.add_edge("reviewer", "input_writer") # Reviewer fixes and resubmits
    workflow.add_edge("visualizer", END)
    
    return workflow.compile()
