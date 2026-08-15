import os
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

class SlurmScriptResult(BaseModel):
    script_content: str = Field(description="The complete Slurm submission script content")

def build_runner_agent():
    llm = ChatOpenAI(
        model="minimax-m27",
        temperature=0.1
    )
    
    prompt = PromptTemplate(
        template="""You are an expert in OpenFOAM and HPC clusters.
Generate a Slurm script based on the provided user requirement. 

User requirement: {user_requirement}

Output ONLY the script content. Ensure that the script is fully functional and matches the specific cluster requirements (e.g., Perlmutter) if mentioned.
""",
        input_variables=["user_requirement"]
    )
    
    chain = prompt | llm.with_structured_output(SlurmScriptResult)
    return chain

def generate_hpc_script(prompt_text: str) -> str:
    """Execute the runner agent to generate a slurm script if HPC is requested."""
    # Only run the heavy LLM call if HPC is actually mentioned to save costs
    if "hpc" not in prompt_text.lower() and "slurm" not in prompt_text.lower() and "cluster" not in prompt_text.lower():
        return "# Local run, no Slurm script needed.\n./Allrun"
        
    chain = build_runner_agent()
    try:
        result = chain.invoke({"user_requirement": prompt_text})
        return result.script_content
    except Exception as e:
        print(f"Runner Agent failed: {e}")
        # Fallback script
        return "#!/bin/bash\n#SBATCH -N 1\n#SBATCH -n 32\n./Allrun -parallel"
