from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class HPCConfig(BaseModel):
    host: str = Field(..., description="SSH host address")
    port: int = Field(22, description="SSH port")
    username: str = Field(..., description="SSH username")
    identity_file: str = Field("~/.ssh/id_rsa", description="Path to SSH private key")
    remote_workdir: str = Field("~/harnessfoam_runs", description="Remote directory to run cases")
    load_modules: str = Field("module load openfoam", description="Command to load OpenFOAM on remote")

class SimulationRequest(BaseModel):
    prompt: str = Field(..., description="Simulation specification text")
    post_prompt: Optional[str] = Field(None, description="Optional post-processing prompt")
    output_dir: Optional[str] = Field(None, description="Directory to save case files")
    llm_kwargs: Optional[Dict[str, Any]] = Field(default_factory=dict, description="LLM settings override")
    target_env: str = Field("local", description="Target compute environment ('local' or 'hpc')")
    hpc_config: Optional[HPCConfig] = Field(None, description="HPC configuration if target_env is 'hpc'")

class SimulationResponse(BaseModel):
    case_id: str = Field(..., description="Unique identifier for the simulation run")
    status: str = Field(..., description="Status of the simulation (e.g. 'PENDING')")
    case_dir: str = Field(..., description="Absolute path to the case directory")

class RunStatus(BaseModel):
    case_id: str
    status: str
    errors: int
    current_step: str
    logs: Dict[str, Any]

class UpdateRequest(BaseModel):
    updates: Dict[str, Any]

class FileContent(BaseModel):
    content: str
