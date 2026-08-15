import json
from pprint import pprint
from harnessfoam.agents.graph import create_workflow, SimulationState

def run_actual_demo():
    print("Initializing LangGraph Workflow...")
    workflow = create_workflow()
    
    initial_state = SimulationState(
        prompt="Perform a 2D incompressible lid driven cavity flow. I need a blockMesh configuration. Also generate an HPC slurm script for Perlmutter and visualize the velocity magnitude.",
        case_id="demo_run_01",
        plan=[],
        mesh_job_id=None,
        run_job_id=None,
        viz_job_id=None,
        status="PENDING",
        logs={},
        errors=0,
        max_errors=3
    )
    
    print("\nStarting execution (this will call the real OpenAI/CSTCloud APIs)...")
    results = workflow.invoke(initial_state)
    
    print("\n" + "="*50)
    print("FINAL EXECUTION LOGS:")
    print("="*50)
    
    logs = results.get('logs', {})
    
    print("\n1. [Architect] Generated File Plan:")
    pprint(results.get('plan', []))
    
    print("\n2. [Meshing] Gmsh Required:")
    print(logs.get('is_gmsh_required'))
    if logs.get('mesh_python_script'):
        print("Script:\n" + logs.get('mesh_python_script')[:200] + "...\n")
        
    print("\n3. [Runner] Generated Slurm Script:")
    print(logs.get('slurm_script', 'None'))
    
    print("\n4. [Visualizer] Generated PyVista Script:")
    print(logs.get('pyvista_script', 'None'))
    
    print("\n5. [Reviewer] Error Fix Suggestions:")
    pprint(logs.get('review_suggestions', []))

if __name__ == "__main__":
    run_actual_demo()
