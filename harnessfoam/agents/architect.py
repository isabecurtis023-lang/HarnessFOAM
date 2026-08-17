import os
from typing import List
from pydantic import BaseModel, Field
from harnessfoam.agents.llm_config import build_llm, create_structured_chain
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
from harnessfoam.knowledge import format_context

# Load environment variables from .env if present
load_dotenv()

class FolderFileStruct(BaseModel):
    file_name: str = Field(description="The name of the OpenFOAM input file")
    folder_name: str = Field(description="The directory where it should be stored (e.g., '0', 'constant', 'system')")

class ArchitectPlan(BaseModel):
    subtasks: List[FolderFileStruct] = Field(description="List of files to generate")

def build_architect_agent(llm_kwargs: dict = None):
    kwargs = (llm_kwargs or {}).copy()
    if 'temperature' not in kwargs: kwargs['temperature'] = 0.1
    llm = build_llm(**kwargs)
    
    prompt = PromptTemplate(
        template="""You are an experienced Planner specializing in OpenFOAM projects.
Your task is to break down the following user requirement into a series of smaller, manageable subtasks.
For each subtask, identify the file name of the OpenFOAM input file (foamfile) and the corresponding folder name where it should be stored.

CRITICAL RULES:
1. You MUST include files in the '0' directory (e.g., U, p).
2. You MUST include files in the 'constant' directory. For OpenFOAM 13 incompressible cases use physicalProperties (legacy releases may use transportProperties); add turbulenceProperties only when the selected solver requires it.
3. You MUST include files in the 'system' directory (e.g., controlDict, fvSchemes, fvSolution, blockMeshDict).

User Requirement: {user_requirement}

Make sure you generate all the necessary files for the user's requirements.
""",
        input_variables=["user_requirement"]
    )
    
    chain = create_structured_chain(llm, prompt, ArchitectPlan)
    return chain
def plan_simulation(prompt_text: str, llm_kwargs: dict = None, memory_context: str = "") -> List[dict]:
    """Execute the architect agent to get a structured plan."""
    chain = build_architect_agent(llm_kwargs=llm_kwargs)
    enriched_prompt = f"{prompt_text}\n\nCanonical retrieved OpenFOAM guidance:\n{format_context(prompt_text, k=5, route='architect')}" + memory_context
    result = chain.invoke({"user_requirement": enriched_prompt})
    return [{"file": item.file_name, "folder": item.folder_name} for item in result.subtasks]
