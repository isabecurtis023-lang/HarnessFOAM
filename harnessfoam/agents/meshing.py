import os
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

class MeshingScriptResult(BaseModel):
    is_gmsh_required: bool = Field(description="True if Gmsh library should be used, False if native OpenFOAM blockMesh/snappyHexMesh is sufficient.")
    python_script: str = Field(description="The complete python script to generate the .msh file using the gmsh library. Empty if not required.")

def build_meshing_agent():
    llm = ChatOpenAI(
        model="DeepSeek-V3.2",
        temperature=0.1
    )
    
    prompt = PromptTemplate(
        template="""You are an expert in computational fluid dynamics and mesh generation.
Analyze the user requirement and decide whether a custom Gmsh python script is required. If the user mentions complex geometries like cylinders, airfoils, or explicitly requests gmsh, set is_gmsh_required to True and write the python script using the `gmsh` API to produce a 'mesh.msh' file.
If it is a simple box cavity or native mesh dictionaries are sufficient, set is_gmsh_required to False.

User requirement: {user_requirement}

Output ONLY the structured JSON. Do not provide explanations.
""",
        input_variables=["user_requirement"]
    )
    
    chain = prompt | llm.with_structured_output(MeshingScriptResult)
    return chain

def generate_mesh_script(prompt_text: str) -> dict:
    """Execute the meshing agent to determine meshing strategy and generate scripts."""
    chain = build_meshing_agent()
    try:
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
