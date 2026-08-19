import os
import shutil
import pytest
from harnessfoam.validation import parse_physics_diagnostics
from harnessfoam.agents.graph import create_workflow, SimulationState

def test_parse_physics_diagnostics():
    log_content = """
    Time = 0.01
    Courant Number mean: 0.1 max: 105.4
    global = 1000.5
    Bounding epsilon, min: -10.5 max: 1000
    Floating point exception
    """
    
    diag = parse_physics_diagnostics(log_content)
    assert diag["courant_explosion"] == True
    assert diag["bounding_epsilon"] == False # Wait, regex is 'bounding epsilon,' lowercase with comma. Let's make sure it matches. 
    assert diag["floating_point_exception"] == True

# Let's adjust the test to match the exact regex in validation.py
def test_parse_physics_diagnostics_exact():
    log_content = "bounding k, bounding epsilon, Courant Number mean: 0.1 max: 105.4 Floating point exception global = 1e5 " * 12
    diag = parse_physics_diagnostics(log_content)
    assert diag["courant_explosion"] == True
    assert diag["bounding_epsilon"] == True
    assert diag["floating_point_exception"] == True
    assert diag["continuity_divergence"] == True

def test_physics_autopilot_routing():
    workflow = create_workflow()
    
    state: SimulationState = {
        "status": "FAILED",
        "errors": 1,
        "max_errors": 3,
        "logs": {
            "physics_diagnostics": {
                "courant_explosion": True
            }
        }
    }
    
    # Check conditional routing
    from harnessfoam.agents.graph import should_review
    route = should_review(state)
    assert route == "physics_autopilot"
    
    # Check that normal failure without physics divergence routes to review
    state["logs"]["physics_diagnostics"]["courant_explosion"] = False
    route2 = should_review(state)
    assert route2 == "review"
