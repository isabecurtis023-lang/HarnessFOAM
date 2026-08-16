import os
from typing import List
from pydantic import BaseModel, Field
from harnessfoam.agents.llm_config import build_llm, create_structured_chain
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

class MeshingScriptResult(BaseModel):
    is_gmsh_required: bool = Field(description="True if Gmsh library should be used, False if native OpenFOAM blockMesh/snappyHexMesh is sufficient.")
    python_script: str = Field(description="The complete python script to generate the .msh file using the gmsh library. Empty if not required.")

def build_meshing_agent(llm_kwargs: dict = None):
    llm = build_llm(temperature=0.1, **(llm_kwargs or {}))
    
    prompt = PromptTemplate(
        template="""You are an expert in computational fluid dynamics and mesh generation.
Analyze the user requirement and decide whether a custom Gmsh python script is required. If the user mentions complex geometries like cylinders, airfoils, or explicitly requests gmsh, set is_gmsh_required to True and write the python script using the `gmsh` API to produce a 'mesh.msh' file.
If it is a simple box cavity or native mesh dictionaries are sufficient, set is_gmsh_required to False.

User requirement: {user_requirement}

Output ONLY the structured JSON. Do not provide explanations.
""",
        input_variables=["user_requirement"]
    )
    
    chain = create_structured_chain(llm, prompt, MeshingScriptResult)
    return chain

def generate_mesh_script(prompt_text: str, case_dir: str = "", llm_kwargs: dict = None) -> dict:
    """Execute the meshing agent to determine meshing strategy and generate scripts."""
    # Check if a valid mesh.py already exists
    if case_dir:
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
                    print(f"Meshing Agent: SKIP mesh.py generation (already exists and passed strict structural validation)", flush=True)
                    return {
                        "is_gmsh_required": True,
                        "python_script": content
                    }
                else:
                    print(f"Meshing Agent: Existing mesh.py is incomplete or invalid. Regenerating...", flush=True)
            except Exception as e:
                print(f"Meshing Agent: Failed to read existing mesh.py: {e}")

    try:
        chain = build_meshing_agent(llm_kwargs=llm_kwargs)
        result = chain.invoke({"user_requirement": prompt_text})
        return {
            "is_gmsh_required": result.is_gmsh_required,
            "python_script": result.python_script
        }
    except Exception as e:
        print(f"Meshing Agent failed: {e}")
        # Fallback mechanism
        return {
            "is_gmsh_required": False,
            "python_script": ""
        }
