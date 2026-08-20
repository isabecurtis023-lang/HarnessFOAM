import os
import logging
import json
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from harnessfoam.agents.llm_config import build_llm, create_structured_chain
from harnessfoam.optimization import run_parameter_sweep

logger = logging.getLogger(__name__)

class OptParameter(BaseModel):
    path: str = Field(description="The relative path to the dictionary, e.g. system/controlDict")
    key: str = Field(description="The exact OpenFOAM keyword to sweep, e.g. deltaT")
    values: List[float] = Field(description="The list of numeric candidate values to test")

class OptSweepPlan(BaseModel):
    parameters: List[OptParameter] = Field(description="The list of parameters to sweep concurrently")
    objective: str = Field(description="The validation metric to track: last_time, max_courant, final_residual, max_abs_continuity_error")
    direction: str = Field(description="The optimization direction: 'max' or 'min'")
    reasoning: str = Field(description="Your physical reasoning for selecting these parameters and bounds")

OPTIMIZER_PROMPT_TEMPLATE = """You are OptMetaOpenFOAM, an intelligent agent for CFD parameter sensitivity analysis.
Your task is to design a bounded parameter sweep to satisfy the user's optimization goal.

Base Case Directory: {base_case}
User Objective: {user_objective}

You must return a structured JSON plan for `run_parameter_sweep`.
Available objective metrics you can target:
- last_time (Useful for maximizing how far a simulation progresses before crashing)
- max_courant (Useful for minimizing the Courant number)
- max_abs_continuity_error (Useful for ensuring mass conservation)
- final_residual (Useful for ensuring solver convergence)

Choose a small set of highly relevant candidate values (e.g., 3-5 values per parameter) to avoid combinatorial explosion.
"""

def generate_sweep_plan(base_case: str, user_objective: str, llm_kwargs: dict = None) -> OptSweepPlan:
    from langchain_core.prompts import PromptTemplate
    
    prompt = PromptTemplate(
        template=OPTIMIZER_PROMPT_TEMPLATE,
        input_variables=["base_case", "user_objective"]
    )
    
    llm = build_llm(temperature=0.1, **(llm_kwargs or {}))
    chain = create_structured_chain(llm, prompt, OptSweepPlan)
    
    return chain.invoke({
        "base_case": base_case,
        "user_objective": user_objective
    })

def run_agentic_optimization(base_case: str, output_root: str, user_objective: str, llm_kwargs: dict = None) -> Dict[str, Any]:
    """Runs a full intelligent optimization loop based on a natural language goal."""
    logger.info(f"OptMetaOpenFOAM Agent: Designing sweep for '{user_objective}'")
    
    try:
        plan = generate_sweep_plan(base_case, user_objective, llm_kwargs)
    except Exception as e:
        logger.error(f"Failed to generate sweep plan: {e}")
        return {"status": "FAILED", "error": f"Plan generation failed: {e}"}
        
    logger.info(f"OptMetaOpenFOAM Plan: sweeping {len(plan.parameters)} parameters to {plan.direction} {plan.objective}")
    
    # Convert Pydantic to raw dicts for the sweep engine
    raw_params = [
        {"path": p.path, "key": p.key, "values": p.values}
        for p in plan.parameters
    ]
    
    try:
        results = run_parameter_sweep(
            base_case=base_case,
            output_root=output_root,
            parameters=raw_params,
            objective=plan.objective,
            direction=plan.direction
        )
        
        # Inject the agent's reasoning into the results for the frontend
        results["agent_reasoning"] = plan.reasoning
        results["agent_plan"] = raw_params
        return results
        
    except Exception as e:
        logger.error(f"Parameter sweep execution failed: {e}")
        return {"status": "FAILED", "error": f"Execution failed: {e}"}

