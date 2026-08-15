# 2026-08-15 - Created by Antigravity (Model: gemini-2.5-pro)
# Test suite for Phase 10: Advanced Multi-Physics Benchmarks

ADVANCED_TEST_CASES = [
    {
        "id": "T06_HEAT_LAMINAR",
        "description": "Buoyancy-driven flow in a differentially heated square cavity (Laminar).",
        "prompt": "Simulate laminar buoyancy-driven convection in a 2D square cavity. The left wall is heated to 300K, the right wall is cooled to 280K, and the top/bottom walls are adiabatic. Use the buoyantBoussinesqPimpleFoam solver with a Prandtl number of 0.71 and Rayleigh number around 1e5. Mesh should be refined near the walls."
    },
    {
        "id": "T07_HEAT_TURBULENT",
        "description": "Turbulent heat transfer over a heated flat plate.",
        "prompt": "Model turbulent air flow at 10 m/s over a heated flat plate at constant temperature 350K. Use buoyantSimpleFoam with the k-omega SST turbulence model. Ensure the mesh has suitable boundary layer grading for y+ ~ 1 near the plate surface to accurately capture the thermal boundary layer."
    },
    {
        "id": "T08_MULTIPHASE_DAM_BREAK",
        "description": "Classic Dam Break simulation using Volume of Fluid (VOF).",
        "prompt": "Setup the classic dam break problem using interFoam. A rectangular column of water (alpha.water=1) is initially at rest behind a barrier that is suddenly removed, collapsing under gravity (g=-9.81 m/s^2) into an empty tank. Track the free surface evolution over 2 seconds with adaptive time-stepping (max Co = 0.5)."
    },
    {
        "id": "T09_MULTIPHASE_DROPLET",
        "description": "Droplet impact on a shallow liquid pool.",
        "prompt": "Simulate a spherical water droplet impacting a shallow liquid pool of the same fluid. Use interFoam and VOF. The droplet has an initial downward velocity of 2 m/s. Capture the resulting splashing and crown formation. Use a fine uniform mesh in the impact region and surface tension effects."
    },
    {
        "id": "T10_COMBUSTION_FLAME",
        "description": "Counter-flow diffusion flame.",
        "prompt": "Configure a counter-flow diffusion flame using reactingFoam. Fuel (Methane, CH4) enters from the top nozzle and oxidizer (Air) enters from the bottom nozzle at equal momenta. Use a single-step global reaction mechanism (CH4 + 2O2 -> CO2 + 2H2O) and the EDC combustion model."
    },
    {
        "id": "T11_SHOCK_SUPERSONIC_STEP",
        "description": "Forward-facing step in supersonic flow.",
        "prompt": "Model a Mach 3 supersonic flow entering a 2D channel and hitting a forward-facing step. Use rhoCentralFoam for high-speed compressible flows. Capture the formation of the detached bow shock and expansion fans. Use an inviscid Euler setup for simplicity with reflecting walls."
    },
    {
        "id": "T12_SHOCK_SOD_TUBE",
        "description": "Sod shock tube Riemann problem.",
        "prompt": "Set up the classic 1D Sod shock tube problem using rhoCentralFoam. A long tube is divided in half: the left side has high pressure (100 kPa) and high density (1 kg/m3), the right side has low pressure (10 kPa) and low density (0.125 kg/m3). Run until t=0.005s to capture the shock wave, contact discontinuity, and expansion wave."
    },
    {
        "id": "T13_TURBULENT_AERO_MOTORBIKE",
        "description": "3D Motorbike generic aerodynamics.",
        "prompt": "Simulate 3D turbulent external aerodynamics around the classic OpenFOAM Motorbike geometry using simpleFoam. Freestream velocity is 20 m/s. Use snappyHexMesh to snap to the motorbike surface. Apply the k-epsilon turbulence model with wall functions. Output the drag and lift force coefficients."
    },
    {
        "id": "T14_LAMINAR_BACKWARD_STEP",
        "description": "Incompressible flow over a backward-facing step.",
        "prompt": "Create a 2D simulation of flow over a backward-facing step using icoFoam. The Reynolds number based on the step height should be exactly 400 to ensure laminar flow. Measure the reattachment length of the primary recirculation zone behind the step."
    },
    {
        "id": "T15_SHALLOW_WATER",
        "description": "Shallow water wave propagation over a bump.",
        "prompt": "Use shallowWaterFoam to simulate a long wave propagating over a parabolic bottom bump in a 2D channel. Initially, the water surface is flat but has a horizontal velocity. Observe the free surface elevation changes (hydraulic jump formation) as it interacts with the bathymetry."
    }
]

def get_advanced_test_cases():
    return ADVANCED_TEST_CASES

if __name__ == "__main__":
    print(f"Loaded {len(ADVANCED_TEST_CASES)} advanced physics test cases.")
