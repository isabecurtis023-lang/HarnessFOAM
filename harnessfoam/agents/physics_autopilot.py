import os
import logging
from typing import Dict
from langchain_core.prompts import ChatPromptTemplate
from harnessfoam.agents.llm_config import build_llm
from harnessfoam.validation import parse_physics_diagnostics

logger = logging.getLogger(__name__)

PHYSICS_AUTOPILOT_PROMPT = """You are an expert OpenFOAM numerical analyst and CFD physicist.
The simulation has failed due to numerical divergence, floating-point exception, or Courant number explosion.

Simulation Directory: {output_dir}
Solver Log Excerpt (end of log):
{error_log}

Diagnostics parsed from the log:
{diagnostics}

Your goal is to apply numerical stabilization strategies to prevent divergence in the next run.
You have the ability to read case files and apply targeted content replacements.

# Numerical Best Practices:
1. **Courant Number Explosion / Continuity Errors**: 
   - Decrease `deltaT` in `system/controlDict`.
   - If using a steady-state solver (simpleFoam), ensure `relaxationFactors` (in `system/fvSolution`) are low enough (e.g., p 0.3, U 0.7, k 0.7).
2. **Turbulence Bounding (bounding k, epsilon, omega)**:
   - This often means initial conditions are bad, or divSchemes are too aggressive.
   - Change `divSchemes` in `system/fvSchemes` from `linear` or `limitedLinear` to `upwind` for `div(phi,U)`, `div(phi,k)`, etc., until the case stabilizes.
3. **Linear Solver Divergence**:
   - If a solver like `GAMG` or `PCG` diverges immediately, try increasing `nOrthogonalCorrectors` in `system/fvSolution`.
   - Ensure `pRefCell` and `pRefValue` are set if the case is closed-domain incompressible.

# Guidelines:
1. First, use `read_file` to inspect `system/controlDict`, `system/fvSchemes`, and `system/fvSolution`.
2. Determine the most likely cause of divergence based on the log and diagnostics.
3. Use `patch_file` to replace the problematic parameters. BE CONSERVATIVE. E.g., if deltaT is 0.01, lower it to 0.005. If scheme is linear, make it upwind.
4. Output a summary of your reasoning and what changes you made.

DO NOT try to run `blockMesh` or `simpleFoam` yourself. Just patch the files. The orchestrator will re-run the simulation.
"""

def run_physics_autopilot(output_dir: str, error_log: str) -> Dict:
    """Invokes the Physics Autopilot agent to fix numerical divergence."""
    from langchain.tools import tool

    logger.info(f"Invoking Physics Autopilot for {output_dir}")
    
    # Parse diagnostics
    diagnostics = parse_physics_diagnostics(error_log)
    
    llm = build_llm(temperature=0.1)
    
    @tool
    def patch_file(filepath: str, old_text: str, new_text: str) -> str:
        """Replace old_text with new_text in the specified case file."""
        import os
        full_path = os.path.join(output_dir, filepath)
        if not os.path.exists(full_path):
            return f"Error: File {filepath} does not exist."
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        if old_text not in content:
            return f"Error: old_text not found in {filepath}."
        content = content.replace(old_text, new_text)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        return f"Successfully patched {filepath}."
        
    @tool
    def read_file(filepath: str) -> str:
        """Read a file from the case directory."""
        import os
        full_path = os.path.join(output_dir, filepath)
        if not os.path.exists(full_path):
            return f"Error: File {filepath} does not exist."
        with open(full_path, "r", encoding="utf-8") as f:
            return f.read()

    tools = [patch_file, read_file]
    llm_with_tools = llm.bind_tools(tools)
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", PHYSICS_AUTOPILOT_PROMPT),
        ("human", "Analyze the divergence and patch the necessary numerical parameters.")
    ])
    
    chain = prompt | llm_with_tools
    
    diag_str = "\\n".join([f"- {k}: {v}" for k, v in diagnostics.items()])
    
    messages = prompt.format_messages(
        output_dir=output_dir,
        error_log=error_log[-2000:], # last 2000 chars is usually enough for FPE
        diagnostics=diag_str
    )
    
    try:
        response = llm_with_tools.invoke(messages)
        tool_calls_made = []
        
        # We need a small loop to handle tool calls and replies.
        # LangChain's basic invoke doesn't auto-loop, so we process it manually.
        current_msg = response
        for _ in range(5): # max 5 tool turns
            if not current_msg.tool_calls:
                break
                
            messages.append(current_msg)
            for tc in current_msg.tool_calls:
                if tc['name'] == 'read_file':
                    res = read_file.invoke(tc['args'])
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "name": tc["name"], "content": res})
                elif tc['name'] == 'patch_file':
                    res = patch_file.invoke(tc['args'])
                    tool_calls_made.append(tc['args'])
                    messages.append({"role": "tool", "tool_call_id": tc["id"], "name": tc["name"], "content": res})
                    
            current_msg = llm_with_tools.invoke(messages)
            
        if tool_calls_made:
            return {
                "status": "APPLIED",
                "reasoning": current_msg.content,
                "patches": tool_calls_made
            }
                
        return {
            "status": "NO_CHANGES",
            "reasoning": current_msg.content,
            "patches": []
        }
    except Exception as e:
        logger.error(f"Physics autopilot failed: {e}")
        return {
            "status": "ERROR",
            "reasoning": str(e),
            "patches": []
        }
