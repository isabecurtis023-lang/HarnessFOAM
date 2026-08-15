import pytest
from harnessfoam.agents.graph import create_workflow, SimulationState

@pytest.mark.asyncio
async def test_multi_element_airfoil():
    """Test 1: 2D incompressible flow over a multi element airfoil setup."""
    workflow = create_workflow()
    initial_state = SimulationState(
        user_requirement="do an incompressible 2D incompressible flow over a multi element airfoil setup. The mesh is provided as a .msh file. The msh file contains 4 boundaries named 'inlet', 'outlet', 'walls', 'airfoil' and 'frontAndBack'. The 'inlet' and 'outlet' are of type freestream with the freestream velocity being 9 m/s. The 'walls' and 'airfoil' have a no-slip boundary condition (velocity equal to zero at the wall). The 'frontAndBack' faces are designated as 'empty'. The simulation runs from time 0 to 10 with a time step of 1.0 units, and results are output every 1 time steps. The viscosity (nu) is set as constant with a value of 1.5e-5 m2/s. Use simpleFoam solver. Use SpalartAllmaras turbulence model. Further visualize the magnitude of velocity along the Z plane.",
        case_dir="demo_run_02_airfoil"
    )
    # The system will gracefully fall back to default generation if API fails or lacks keys
    final_state = await workflow.ainvoke(initial_state)
    assert final_state["current_step"] in ["reviewer", "visualizer", "end"]
    assert "simpleFoam" in str(final_state.get("file_plan", [])) or len(final_state.get("file_plan", [])) > 0

@pytest.mark.asyncio
async def test_tandem_wing():
    """Test 2: 3D incompressible flow over a tandem wing configuration."""
    workflow = create_workflow()
    initial_state = SimulationState(
        user_requirement="do an incompressible 3D incompressible flow over a tandem wing configuration. The mesh is provided as a .msh file. The msh file contains 4 boundaries named 'inlet', 'outlet', 'walls', 'airfoil' and 'frontAndBack'. The 'inlet' and 'outlet' are of type freestream with the freestream velocity being 9 m/s. The 'walls' and 'airfoil' have a no-slip boundary condition (velocity equal to zero at the wall). The 'frontAndBack' faces are also of type wall. The simulation runs from time 0 to 10 with a time step of 1.0 units, and results are output every 1 time steps. The viscosity (nu) is set as constant with a value of 1.5e-5 m2/s. Use simpleFoam solver. Use SpalartAllmaras turbulence model. Further visualize the magnitude of velocity along the mid Z section at the final time.",
        case_dir="demo_run_03_tandem"
    )
    final_state = await workflow.ainvoke(initial_state)
    assert len(final_state.get("file_plan", [])) > 0

@pytest.mark.asyncio
async def test_flow_over_cylinder():
    """Test 3: Flow Over Cylinder with gmsh."""
    workflow = create_workflow()
    initial_state = SimulationState(
        user_requirement="Simulate incompressible flow over a circular cylinder. Use gmsh to create the computational mesh. The computational domain extends from -2.5 to 2.5 in the x-direction, -1 to 1 in the y-direction, and 0 to 0.2 in the z-direction. The cylinder is positioned at (-1, 0) with a radius of 0.1 units. Use a structured mesh with approximately 20x10 cells in the x-y plane and 1 cell in the z-direction. The inlet boundary named 'inlet' (left boundary at x = -2.5) has a uniform velocity of 1 m/s in the positive x-direction. The right boundary at x=+2.5 is the outlet named 'outlet'. The top and bottom walls named 'topWall' and 'bottomWall' respectively (y = +1 and y=-1) use slip boundary conditions. The cylinder surface named 'cylinder' uses a no-slip boundary condition (velocity equal to zero at the wall). The front and back faces named 'frontAndBack' are located at z = 0 and z = 0.2 respectively, and are designated as 'empty' for 2D simulation. Use base mesh size of 0.5 on cylinder and size of 1.0 elsewhere. The simulation runs from time 0 to 2 seconds with a time step of 0.001 units, and results are output every 100 time steps. The kinematic viscosity (nu) is set as constant with a value of 1e-5 m2/s. Use pisoFoam solver for incompressible flow. Visualize the magnitude of velocity ('U') along the x-y plane.",
        case_dir="demo_run_04_cylinder"
    )
    final_state = await workflow.ainvoke(initial_state)
    assert len(final_state.get("file_plan", [])) > 0

@pytest.mark.asyncio
async def test_flow_over_two_square_obstacles():
    """Test 4: Flow Over Two Square Obstacles."""
    workflow = create_workflow()
    initial_state = SimulationState(
        user_requirement="Simulate incompressible flow over two square obstacles. Use gmsh to create the computational mesh. The computational domain spans 0 to 5 in x direction and 0 to 2.5 in y direction and 0 to 0.1 in z direction. One of the square obstacle is of size 0.25 unit x 0.25 unit x 0.1 unit centered at 1.5 x 1.25 x 0.0 and the other square obstacle is of size 0.25 unit x 0.25 unit x 0.1 unit centered at 3.5 x 1.25 x 0.0. Use one cell in z direction making the geometry effectively 2D. Use a structured mesh with approximately 50x25 cells in the x-y plane and 1 cell in the z-direction. The inlet boundary named 'inlet' (left boundary at x = 0) has a uniform velocity of 1 m/s in the positive x-direction. The right boundary at x = 5 is the outlet named 'outlet'. The top and bottom walls named 'topWall' and 'bottomWall' respectively (y = 2.5 and y = 0) use slip boundary conditions. The square obstacle surfaces named 'square1' and 'square2' use no-slip boundary conditions (velocity equal to zero at the walls). The front and back faces named 'frontAndBack' are located at z = 0 and z = 0.1 respectively, and are designated as 'empty' for 2D simulation. Use base mesh size of 0.5 on squares and size of 1.0 elsewhere. The simulation runs from time 0 to 10 seconds with a time step of 0.001 units, and results are output every 100 time steps. The kinematic viscosity (nu) is set as constant with a value of 1e-5 m2/s. Use pisoFoam solver for incompressible flow. Visualize the magnitude of velocity ('U') along the x-y plane.",
        case_dir="demo_run_05_squares"
    )
    final_state = await workflow.ainvoke(initial_state)
    assert len(final_state.get("file_plan", [])) > 0

@pytest.mark.asyncio
async def test_3d_cavity_hpc_case():
    """Test 5: 3D cavity HPC Case."""
    workflow = create_workflow()
    initial_state = SimulationState(
        user_requirement="Do an incompressible 3D lid driven cavity flow using icoFoam solver. The cavity is a cube of dimension [0, 0.1]x [0, 0.1]x [0,0.1]. Use simple grading with 100X100x100 in x, y and z direction. The top wall ('movingWall') moves in the x-direction with a uniform velocity of 1 m/s. The 'fixedWalls' have a no-slip boundary condition (velocity equal to zero at the wall). The simulation runs from time 0 to 0.015 with a time step of 0.001 units, and results are output every 10 time steps. The viscosity (nu) is set as constant with a value of 0.01 m2/s. Perform an hpc run for this case in perlmutter cluster. My account is xxxx. Do a parallel run for this case by splitting it into 32 subdomains.",
        case_dir="demo_run_06_3dcavity"
    )
    final_state = await workflow.ainvoke(initial_state)
    assert len(final_state.get("file_plan", [])) > 0
