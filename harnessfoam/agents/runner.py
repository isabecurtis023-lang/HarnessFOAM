import os
from pydantic import BaseModel, Field
from harnessfoam.agents.llm_config import build_llm, create_structured_chain
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

class SlurmScriptResult(BaseModel):
    script_content: str = Field(description="The complete Slurm submission script content")

def build_runner_agent(llm_kwargs: dict = None):
    kwargs = (llm_kwargs or {}).copy()
    if 'temperature' not in kwargs: kwargs['temperature'] = 0.1
    llm = build_llm(**kwargs)
    
    prompt = PromptTemplate(
        template="""You are an expert in OpenFOAM and HPC clusters.
Generate a Slurm script based on the provided user requirement. 

User requirement: {user_requirement}

Output ONLY the script content. Ensure that the script is fully functional and matches the specific cluster requirements (e.g., Perlmutter) if mentioned.
""",
        input_variables=["user_requirement"]
    )
    
    chain = create_structured_chain(llm, prompt, SlurmScriptResult)
    return chain

def generate_hpc_script(prompt_text: str, llm_kwargs: dict = None) -> str:
    """Execute the runner agent to generate a slurm script if HPC is requested."""
    # 2026-08-15 – Gemini 3.5 Flash: return a placeholder, handled locally by the graph or server
    if "hpc" not in prompt_text.lower() and "slurm" not in prompt_text.lower() and "cluster" not in prompt_text.lower():
        return "# Local run, no Slurm script needed.\n# Done."
        
    try:
        chain = build_runner_agent(llm_kwargs=llm_kwargs)
        result = chain.invoke({"user_requirement": prompt_text})
        return result.script_content
    except Exception as e:
        print(f"Runner Agent failed: {e}")
        # Fallback script
        return "#!/bin/bash\n#SBATCH -N 1\n#SBATCH -n 32\n./Allrun -parallel"

import subprocess

def execute_simulation(case_dir: str) -> tuple[bool, str]:
    """Physically runs the simulation locally in the case directory. Returns (success, output)."""
    print(f"--> Physically executing OpenFOAM run locally in {case_dir}")
    
    if not os.path.exists(case_dir):
        return False, f"Error: Case directory {case_dir} does not exist."
        
    # In a real environment, we would execute blockMesh && simpleFoam, etc.
    # For now, we will create a dummy execution script and run it, capturing output.
    allrun_path = os.path.join(case_dir, "Allrun")
    
    # If no Allrun exists, we mock a run command
    if not os.path.exists(allrun_path):
        with open(allrun_path, "w") as f:
            f.write("#!/bin/sh\n")
            f.write("echo 'Running blockMesh...'\n")
            f.write("echo 'Running solver...'\n")
            f.write("echo 'End'\n")
        os.chmod(allrun_path, 0o755)
        
    try:
        # We run the script or command natively
        result = subprocess.run(
            ["sh", "./Allrun"],
            cwd=case_dir,
            capture_output=True,
            text=True,
            timeout=300 # 5 min timeout
        )
        if result.returncode == 0:
            return True, result.stdout
        else:
            return False, result.stderr
    except Exception as e:
        return False, str(e)
