from typing import TypedDict, List, Dict, Any, Optional
import os
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
    memory_enabled: bool
    memory_limits: Dict[str, int]
    retry_history: List[Dict[str, Any]]

from harnessfoam.agents.architect import plan_simulation
from harnessfoam.validation import validate_case_files, validate_runtime
from harnessfoam.case_manifest import write_manifest
from harnessfoam.postprocess import collect_postprocess_metrics
from harnessfoam.physics_validation import validate_physics
from harnessfoam.failure_ledger import summarize_failure_ledger
from harnessfoam.reference_benchmarks import evaluate_reference_case
from harnessfoam.memory import record_event, record_self_improvement, initialize_memory, prompt_context

def _memory_event(state: SimulationState, agent: str, outcome: str, details: str = "") -> None:
    if not state.get('memory_enabled') or not state.get('case_dir'):
        return
    path = record_event(state['case_dir'], agent, outcome=outcome, details=details,
                        enabled=True, limits=state.get('memory_limits') or {})
    if path:
        state.setdefault('logs', {})['memory'] = {'enabled': True, 'last_path': path}

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
    if state.get('memory_enabled') and state.get('case_dir'):
        state.setdefault('logs', {})['memory_documents'] = initialize_memory(
            state['case_dir'], enabled=True, limits=state.get('memory_limits') or {})
    state['current_step'] = 'architect'
    _memory_event(state, 'architect', 'started', state.get('prompt', ''))

    print(f"Architect Agent: Planning simulation for case {state['case_id']}")
    llm_kwargs = state.get('llm_kwargs') or {}
    memory = prompt_context(state.get('case_dir'), 'architect', enabled=bool(state.get('memory_enabled')), limits=state.get('memory_limits') or {})
    state['plan'] = plan_simulation(state['prompt'], llm_kwargs=llm_kwargs, memory_context=memory)
    state['file_plan'] = state['plan']
    print(f"Architect plan generated: {len(state['plan'])} files.")
    _memory_event(state, 'architect', 'success', f"generated {len(state['plan'])} files")
    return state

from harnessfoam.agents.meshing import generate_mesh_script
from harnessfoam.agents.visualizer import generate_visualization_script

def meshing_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'meshing'
    _memory_event(state, 'meshing', 'started', state.get('prompt', ''))
    print(f"Meshing Agent: Generating mesh for case {state['case_dir']}")
    llm_kwargs = state.get('llm_kwargs') or {}
    case_dir = state.get('case_dir', '')
    suggestions = state.get('logs', {}).get('review_suggestions', [])
    mesh_results = generate_mesh_script(state['prompt'], case_dir=case_dir, llm_kwargs=llm_kwargs, review_suggestions=suggestions,
                                        memory_context=prompt_context(case_dir, 'meshing', enabled=bool(state.get('memory_enabled')), limits=state.get('memory_limits') or {}))
    state['logs']['is_gmsh_required'] = mesh_results['is_gmsh_required']
    state['logs']['mesh_script'] = mesh_results['python_script']
    
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
    _memory_event(state, 'input_writer', 'started', state.get('prompt', ''))
    print(f"Input Writer Agent: Generating files for {len(state['plan'])} configurations")
    llm_kwargs = state.get('llm_kwargs') or {}
    case_dir = state.get('case_dir', '')
    suggestions = state.get('logs', {}).get('review_suggestions', [])
    state['logs']['generated_files'] = write_simulation_inputs(
        state['plan'], 
        state['prompt'], 
        case_dir=case_dir, 
        llm_kwargs=llm_kwargs,
        review_suggestions=suggestions,
        memory_context=prompt_context(case_dir, 'input_writer', enabled=bool(state.get('memory_enabled')), limits=state.get('memory_limits') or {})
    )
    
    # Write files to disk
    import os
    import shutil
    case_dir = state.get('case_dir')
    if case_dir:
        os.makedirs(case_dir, exist_ok=True)
        backup_dir = os.path.join(case_dir, '.harnessfoam', 'backups', f"attempt_{state.get('errors', 0)}")
        os.makedirs(backup_dir, exist_ok=True)
        for rel_path in state['logs']['generated_files']:
            old_path = os.path.join(case_dir, rel_path.lstrip('/\\'))
            if os.path.isfile(old_path):
                backup_path = os.path.join(backup_dir, rel_path.lstrip('/\\'))
                os.makedirs(os.path.dirname(backup_path), exist_ok=True)
                shutil.copy2(old_path, backup_path)
        state['logs']['backup_dir'] = backup_dir
        for rel_path, content in state['logs']['generated_files'].items():
            safe_rel_path = rel_path.lstrip("/\\")
            full_path = os.path.join(case_dir, safe_rel_path)
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            # 2026-08-15 – Gemini 3.5 Flash: write with LF endings to prevent WSL errors
            with open(full_path, "w", newline="\n", encoding="utf-8") as f:
                f.write(content)
                
    state['file_plan'] = state['plan']
    return state

def preflight_node(state: SimulationState) -> SimulationState:
    """Validate generated files before launching any external solver."""
    state['current_step'] = 'preflight'
    ok, errors = validate_case_files(state['case_dir'], state.get('plan', []))
    state['logs']['preflight_ok'] = ok
    state['logs']['preflight_errors'] = errors
    if ok:
        state['logs']['manifest'] = write_manifest(state['case_dir'], runtime="WSL" if __import__('shutil').which('wsl') else "Native")
    if not ok:
        state['status'] = 'FAILED'
        state['logs']['execution_error'] = "Preflight validation failed:\n" + "\n".join(errors)
        print("Preflight validation failed:", errors)
    return state

from harnessfoam.agents.runner import generate_hpc_script, execute_simulation
from harnessfoam.agents.reviewer import analyze_errors

def runner_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'runner'
    print(f"Runner Agent: Generating run script...")
    state['run_job_id'] = f"run_{state['case_id']}_{int(time.time())}"
    
    llm_kwargs = state.get('llm_kwargs') or {}
    slurm_script = generate_hpc_script(state['prompt'], llm_kwargs=llm_kwargs,
                                       memory_context=prompt_context(state.get('case_dir'), 'runner', enabled=bool(state.get('memory_enabled')), limits=state.get('memory_limits') or {}))
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
                
        local_script = f"""#!/bin/bash
set -e
# Local execution script generated by HarnessFOAM
# 2026-08-15 – Gemini 3.5 Flash

# Source OpenFOAM environment in WSL/Linux if not already set
if [ -z "$WM_PROJECT_DIR" ]; then
    for foamrc in /opt/openfoam13/etc/bashrc /opt/openfoam*/etc/bashrc; do
        if [ -f "$foamrc" ]; then . "$foamrc" 2>/dev/null || true; break; fi
    done
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
        except: pass
        
                # Actually execute the script locally with streaming
        import subprocess
        import asyncio
        
        # Try to extract the websocket from llm_kwargs callbacks to stream logs
        websocket = None
        loop = None
        try:
            callbacks = state.get('llm_kwargs', {}).get('callbacks', [])
            print(f"[Runner Debug] Callbacks present: {bool(callbacks)}")
            if callbacks:
                websocket = getattr(callbacks[0], 'websocket', None)
                loop = getattr(callbacks[0], 'loop', None)
                print(f"[Runner Debug] websocket={websocket}, loop={loop}")
        except Exception as e:
            print(f"[Runner Debug] Exception extracting callbacks: {e}")

        # Determine the correct shell executor based on OS
        import shutil
        if shutil.which("wsl"):
            # subprocess keeps the Windows cwd; explicitly translate it so the
            # WSL process runs in the case directory rather than /mnt/c/... by
            # accident (and so relative OpenFOAM paths resolve consistently).
            abs_case_dir = os.path.abspath(state['case_dir'])
            if len(abs_case_dir) >= 2 and abs_case_dir[1] == ':':
                wsl_case_dir = "/mnt/" + abs_case_dir[0].lower() + abs_case_dir[2:].replace('\\', '/')
            else:
                wsl_case_dir = abs_case_dir
            cmd = ["wsl", "bash", "-lc", f"cd '{wsl_case_dir}' && bash ./Allrun"]
        elif shutil.which("bash"):
            cmd = ["bash", "./Allrun"]
        else:
            cmd = ["sh", "./Allrun"]

        try:
            process = subprocess.Popen(
                cmd,
                cwd=state['case_dir'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1
            )
            
            run_output = []
            for line in process.stdout:
                line_clean = line.rstrip()
                run_output.append(line_clean)
                print(f"[OpenFOAM] {line_clean}")
                if websocket and loop:
                    try:
                        asyncio.run_coroutine_threadsafe(
                            websocket.send_json({
                                "type": "openfoam_log",
                                "message": line_clean,
                                "is_error": False
                            }),
                            loop
                        )
                    except Exception:
                        pass
                        
            process.wait(timeout=300)
            state['logs']['run_stdout'] = "\n".join(run_output)
            state['logs']['run_stderr'] = ""
            if process.returncode != 0:
                state['status'] = 'FAILED'
                state['logs']['execution_error'] = state['logs']['run_stdout'][-2000:] # Pass the tail of the log to reviewer
                print(f"Runner Agent failed with code {process.returncode}")
            else:
                runtime_ok, metrics, metric_errors = validate_runtime(state['logs']['run_stdout'], expected_version="13")
                state['logs']['runtime_metrics'] = metrics
                physics_ok, physics_metrics, physics_errors = validate_physics(
                    state['case_dir'], state.get('prompt', ''), solver_name
                )
                state['logs']['physics_metrics'] = physics_metrics
                benchmark_ok, benchmark_metrics, benchmark_errors = evaluate_reference_case(
                    state.get('prompt', ''), metrics, physics_metrics
                )
                state['logs']['benchmark_metrics'] = benchmark_metrics
                if not physics_ok:
                    metric_errors.extend(physics_errors)
                if not benchmark_ok:
                    metric_errors.extend([f"Reference benchmark: {error}" for error in benchmark_errors])
                if runtime_ok:
                    state['status'] = 'SUCCESS' if not metric_errors else 'FAILED'
                else:
                    state['status'] = 'FAILED'
                    state['logs']['execution_error'] = "Runtime validation failed:\n" + "\n".join(metric_errors)
        except Exception as e:
            state['status'] = 'FAILED'
            state['logs']['run_stderr'] = str(e)
            state['logs']['execution_error'] = str(e)
            print(f"Runner Agent execution exception: {e}")
            
    else:
        with open(allrun_path, "w", newline="\n", encoding="utf-8") as f:
            f.write(slurm_script)
            
        try:
            os.chmod(allrun_path, 0o755)
        except: pass
        
        state['status'] = 'SUCCESS'
    
    return state

def reviewer_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'reviewer'
    _memory_event(state, 'reviewer', 'started', state.get('logs', {}).get('execution_error', ''))
    print(f"Reviewer Agent: Analyzing errors...")
    state['errors'] += 1
    
    error_logs = state['logs'].get('execution_error', 'Unknown error')
    llm_kwargs = state.get('llm_kwargs') or {}
    review_results = analyze_errors(error_logs, llm_kwargs=llm_kwargs, memory_context=prompt_context(state.get('case_dir'), 'reviewer', enabled=bool(state.get('memory_enabled')), limits=state.get('memory_limits') or {}))
    state['logs']['review_suggestions'] = review_results['suggestions']
    state.setdefault('retry_history', []).append({
        'attempt': state['errors'],
        'error': error_logs[-2000:],
        'suggestions': review_results['suggestions'],
        'status': 'RETRY_PENDING' if state['errors'] < state.get('max_errors', 3) else 'RETRY_EXHAUSTED',
    })
    # Keep a local failure ledger for reproducible retries and future active
    # learning; do not store prompts or logs outside the selected case.
    import json
    ledger_path = os.path.join(state['case_dir'], '.harnessfoam', 'failure_ledger.jsonl')
    os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
    with open(ledger_path, 'a', encoding='utf-8', newline='') as ledger:
        ledger.write(json.dumps({
            'attempt': state['errors'],
            'prompt': state.get('prompt', ''),
            'error': error_logs[-4000:],
            'suggestions': review_results['suggestions'],
        }, ensure_ascii=False) + '\n')
    state['logs']['failure_ledger'] = ledger_path
    state['logs']['failure_ledger_summary'] = summarize_failure_ledger(state['case_dir'])
    if state.get('memory_enabled'):
        record_self_improvement(state['case_dir'], agent='reviewer', error=error_logs,
                                fix=str(review_results['suggestions']), enabled=True,
                                limits=state.get('memory_limits') or {})
    print(f"Reviewer found {len(review_results['suggestions'])} fixes to apply.")
    return state

from harnessfoam.agents.visualizer import execute_visualization
from harnessfoam.agents.reviewer import analyze_visual_anomalies

def visualizer_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'visualizer'
    _memory_event(state, 'visualizer', 'started', state.get('post_prompt', ''))
    print(f"Visualization Agent: Generating visuals...")
    
    # If the user provided a custom post-processing prompt, use it; else use the main prompt
    viz_prompt = state.get('post_prompt') or (
        f"{state.get('prompt', '')}\nAutomatically post-process the completed case and render the velocity field U."
    )
    
    llm_kwargs = state.get('llm_kwargs') or {}
    viz_results = generate_visualization_script(viz_prompt, llm_kwargs=llm_kwargs,
                                                memory_context=prompt_context(state.get('case_dir'), 'visualizer', enabled=bool(state.get('memory_enabled')), limits=state.get('memory_limits') or {}))
    state['logs']['is_visualization_required'] = viz_results['is_visualization_required']
    state['logs']['pyvista_script'] = viz_results['pyvista_script']
    
    # Deep Driving always runs the post-processing agent after a successful
    # solver run.  The model may still choose the field and plot style, but it
    # cannot accidentally disable the automatic post-processing stage.
    if state['status'] == 'SUCCESS':
        print("Visualizer Agent generated PyVista script. Executing locally...")
        img_base64 = execute_visualization(state['case_dir'], viz_results['pyvista_script'])
        if img_base64:
            state['image_base64'] = img_base64
            state['logs']['postprocess_status'] = 'SUCCESS'
            state['logs']['postprocess_metrics'] = collect_postprocess_metrics(state['case_dir'])
            visual_review = analyze_visual_anomalies(
                os.path.join(state['case_dir'], 'visualization.png'),
                state.get('prompt', ''),
                llm_kwargs=llm_kwargs,
            )
            state['logs']['visual_review'] = visual_review
            if visual_review.get('visual_review_status') == 'FAILED':
                state['status'] = 'FAILED'
                state['logs']['execution_error'] = 'Visual physics review failed:\n' + visual_review.get('vlm_feedback', '')
            print("Visualization successfully rendered.")
        else:
            state['logs']['postprocess_status'] = 'FAILED'
            state['logs']['postprocess_error'] = 'Visualizer script did not produce visualization.png'
    else:
        print("No visualization requested or simulation failed.")
        state['logs']['postprocess_status'] = 'SKIPPED'
        
    state['viz_job_id'] = f"viz_{state['case_id']}_{int(time.time())}"
    return state

def end_node(state: SimulationState) -> SimulationState:
    state['current_step'] = 'end'
    if state.get('memory_enabled') and state.get('case_dir'):
        outcome = 'success' if state.get('status') == 'SUCCESS' else 'failed'
        for agent in ('architect', 'meshing', 'input_writer', 'preflight', 'runner', 'visualizer'):
            record_event(state['case_dir'], agent, outcome=outcome,
                         details=f"workflow ended with status={state.get('status')}",
                         enabled=True, limits=state.get('memory_limits') or {})
    return state

def should_review(state: SimulationState) -> str:
    if state['status'] == 'FAILED' and state['errors'] < state['max_errors']:
        return "review"
    elif state['status'] == 'FAILED':
        return "fail"
    return "visualize"

def route_after_review(state: SimulationState) -> str:
    suggestions = state['logs'].get('review_suggestions', [])
    if any(s.get('file') == 'mesh.py' for s in suggestions):
        print("Reviewer requested fix for mesh.py, routing to Meshing Agent...", flush=True)
        return "meshing"
    return "input_writer"

def route_after_preflight(state: SimulationState) -> str:
    return "review" if state.get('status') == 'FAILED' else "run"

def route_after_visualizer(state: SimulationState) -> str:
    return "review" if state.get('status') == 'FAILED' and state.get('errors', 0) < state.get('max_errors', 3) else "end"

def create_workflow() -> StateGraph:
    workflow = StateGraph(SimulationState)
    
    workflow.add_node("architect", architect_node)
    workflow.add_node("meshing", meshing_node)
    workflow.add_node("input_writer", input_writer_node)
    workflow.add_node("runner", runner_node)
    workflow.add_node("preflight", preflight_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("visualizer", visualizer_node)
    workflow.add_node("end", end_node)
    
    workflow.set_entry_point("architect")
    workflow.add_edge("architect", "meshing")
    workflow.add_edge("meshing", "input_writer")
    workflow.add_edge("input_writer", "preflight")
    workflow.add_conditional_edges(
        "preflight",
        route_after_preflight,
        {"review": "reviewer", "run": "runner"}
    )
    
    workflow.add_conditional_edges(
        "runner",
        should_review,
        {
            "review": "reviewer",
            "visualize": "visualizer",
            "fail": "end"
        }
    )
    workflow.add_conditional_edges(
        "reviewer",
        route_after_review,
        {
            "meshing": "meshing",
            "input_writer": "input_writer"
        }
    )
    workflow.add_conditional_edges("visualizer", route_after_visualizer, {"review": "reviewer", "end": "end"})
    workflow.add_edge("end", END)
    
    return workflow.compile()
