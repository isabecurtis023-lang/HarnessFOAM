import argparse
import json
import logging
from pprint import pprint
from harnessfoam.agents.graph import create_workflow, SimulationState

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("HarnessFOAM-Demo")

PRESETS = {
    "cavity": {
        "description": "2D incompressible lid-driven cavity flow",
        "prompt": "Perform a 2D incompressible lid driven cavity flow. I need a blockMesh configuration. Also generate an HPC slurm script for Perlmutter and visualize the velocity magnitude."
    },
    "cylinder": {
        "description": "2D flow over a circular cylinder (Karman vortex street)",
        "prompt": "Simulate 2D incompressible transient flow over a circular cylinder at Re=100. Use pimpleFoam and generate a custom gmsh script for the mesh. Set up probing for lift and drag coefficients."
    },
    "ahmed": {
        "description": "3D Ahmed body aerodynamics",
        "prompt": "Set up a 3D aerodynamic simulation for an Ahmed body using simpleFoam and the k-omega SST turbulence model. Generate snappyHexMesh dictionaries for refinement."
    },
    "heat": {
        "description": "Natural convection in a heated cavity",
        "prompt": "Simulate natural convection of air in a 2D square cavity where the left wall is hot and right wall is cold using buoyantBoussinesqPimpleFoam."
    }
}

def run_actual_demo(scenario_name: str, custom_prompt: str = None):
    logger.info("=" * 60)
    logger.info("🌊 HarnessFOAM CLI Demonstration")
    logger.info("=" * 60)
    
    prompt = custom_prompt
    if not prompt:
        if scenario_name not in PRESETS:
            logger.error(f"Unknown preset: {scenario_name}. Available presets: {list(PRESETS.keys())}")
            return
        logger.info(f"Selected Scenario: {scenario_name.upper()} - {PRESETS[scenario_name]['description']}")
        prompt = PRESETS[scenario_name]['prompt']

    logger.info(f"Target Prompt:\n\n{prompt}\n")
    logger.info("Initializing LangGraph Workflow...")
    
    workflow = create_workflow()
    
    initial_state = SimulationState(
        prompt=prompt,
        case_id=f"demo_run_{scenario_name}",
        plan=[],
        mesh_job_id=None,
        run_job_id=None,
        viz_job_id=None,
        status="PENDING",
        logs={},
        errors=0,
        max_errors=3
    )
    
    logger.info("Starting multi-agent execution pipeline...")
    logger.info("(Connecting to LLM APIs - this might take a minute depending on the prompt complexity)")
    
    results = workflow.invoke(initial_state)
    
    logger.info("="*60)
    logger.info("🏁 FINAL EXECUTION RESULTS:")
    logger.info("="*60)
    
    logs = results.get('logs', {})
    
    print("\n\033[96m1. [Architect] Generated File Plan:\033[0m")
    pprint(results.get('plan', []))
    
    print("\n\033[92m2. [Meshing] Mesh Strategy:\033[0m")
    print(f"Gmsh Required: {logs.get('is_gmsh_required', False)}")
    if logs.get('mesh_python_script'):
        print("\nGenerated Meshing Script Snippet:")
        print(logs.get('mesh_python_script')[:300] + "...\n")
        
    print("\n\033[93m3. [Runner] Execution Scripts:\033[0m")
    print("Slurm Script generated:")
    print(logs.get('slurm_script', 'None'))
    
    print("\n\033[95m4. [Visualizer] Post-Processing:\033[0m")
    print("PyVista Script Snippet:")
    pv_script = logs.get('pyvista_script', 'None')
    if len(pv_script) > 300:
        print(pv_script[:300] + "...\n")
    else:
        print(pv_script)
    
    print("\n\033[91m5. [Reviewer] Automated Error Fix Suggestions:\033[0m")
    suggestions = logs.get('review_suggestions', [])
    if not suggestions:
        print("No errors detected during simulated execution.")
    else:
        pprint(suggestions)
        
    logger.info("Demonstration completed successfully.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run a HarnessFOAM demonstration workflow.")
    parser.add_argument("--scenario", "-s", type=str, default="cavity", 
                        choices=list(PRESETS.keys()),
                        help="Select a predefined CFD scenario to simulate.")
    parser.add_argument("--prompt", "-p", type=str, default=None,
                        help="Provide a custom natural language prompt instead of a preset.")
    
    args = parser.parse_args()
    
    run_actual_demo(args.scenario, args.prompt)
