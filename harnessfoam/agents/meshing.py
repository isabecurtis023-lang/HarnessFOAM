import os
from typing import List
from pydantic import BaseModel, Field
from harnessfoam.agents.llm_config import build_llm, create_structured_chain
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
import logging
logger = logging.getLogger(__name__)


load_dotenv()

class MeshingScriptResult(BaseModel):
    is_gmsh_required: bool = Field(description="True if Gmsh library should be used, False if native OpenFOAM blockMesh/snappyHexMesh is sufficient.")
    python_script: str = Field(description="The complete python script to generate the .msh file using the gmsh library. Empty if not required.")

def build_meshing_agent(llm_kwargs: dict = None):
    kwargs = (llm_kwargs or {}).copy()
    if 'temperature' not in kwargs: kwargs['temperature'] = 0.1
    llm = build_llm(**kwargs)
    
    prompt = PromptTemplate(
        template="""You are an expert in computational fluid dynamics and mesh generation.
Analyze the user requirement and decide whether a custom Gmsh python script is required. If the user mentions complex geometries like cylinders, airfoils, or explicitly requests gmsh, set is_gmsh_required to True and write the python script using the `gmsh` API to produce a 'mesh.msh' file.
If it is a simple box cavity or native mesh dictionaries are sufficient, set is_gmsh_required to False.

CRITICAL GMSH RULES:
1. Do NOT reference non-existent tags (e.g. Physical Curve -1). Always create geometries and capture their returned tags, then use those exact tags.
2. Ensure you properly define Physical Groups for all boundaries (e.g., 'inlet', 'outlet', 'topAndBottom', 'cylinder') and 'internalField' for the fluid volume.
3. The script must initialize gmsh (`gmsh.initialize()`) and write the mesh (`gmsh.write("mesh.msh")`) before `gmsh.finalize()`.
4. Ensure 2D meshes are exactly one cell thick in the Z-direction if requested as 2D.

User requirement: {user_requirement}

Output ONLY the structured JSON. Do not provide explanations.
""",
        input_variables=["user_requirement", "review_context"]
    )
    
    chain = create_structured_chain(llm, prompt, MeshingScriptResult)
    return chain

def generate_mesh_script(prompt_text: str, case_dir: str = "", llm_kwargs: dict = None, review_suggestions: list = None, memory_context: str = "") -> dict:
    """Execute the meshing agent to determine meshing strategy and generate scripts."""
    review_suggestions = review_suggestions or []
    
    # Check if there's a specific fix instruction for mesh.py
    specific_suggestion = ""
    for sugg in review_suggestions:
        if sugg.get("file") == "mesh.py":
            specific_suggestion = sugg.get("fix", "")
            break
            
    # Check if a valid mesh.py already exists
    if not specific_suggestion and case_dir:
        import os
        mesh_script_path = os.path.join(case_dir, "mesh.py")
        if os.path.exists(mesh_script_path):
            try:
                with open(mesh_script_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                
                # Rigorous check: verify it's a complete gmsh script
                required_tokens = [
                    "import gmsh", 
                    "gmsh.initialize", 
                    "gmsh.write", 
                    "gmsh.finalize"
                ]
                
                if all(token in content for token in required_tokens):
                    logger.info(f"Meshing Agent: SKIP mesh.py generation (already exists and passed strict structural validation)")
                    return {
                        "is_gmsh_required": True,
                        "python_script": content
                    }
                else:
                    logger.info(f"Meshing Agent: Existing mesh.py is incomplete or invalid. Regenerating...")
            except Exception as e:
                logger.info(f"Meshing Agent: Failed to read existing mesh.py: {e}")

    try:
        chain = build_meshing_agent(llm_kwargs=llm_kwargs)
        review_context = f"\nReview feedback to incorporate: {specific_suggestion}" if specific_suggestion else ""
        review_context += memory_context
        result = chain.invoke({"user_requirement": prompt_text, "review_context": review_context})
        return {
            "is_gmsh_required": result.is_gmsh_required,
            "python_script": result.python_script
        }
    except Exception as e:
        logger.info(f"Meshing Agent failed: {e}")
        # Fallback mechanism
        return {
            "is_gmsh_required": False,
            "python_script": ""
        }
