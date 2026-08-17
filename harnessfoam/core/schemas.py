from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class SimulationRequest(BaseModel):
    prompt: str = Field(..., description="Simulation specification text")
    post_prompt: Optional[str] = Field(None, description="Optional post-processing prompt")
    output_dir: Optional[str] = Field(None, description="Directory to save case files")
    llm_kwargs: Optional[Dict[str, Any]] = Field(default_factory=dict, description="LLM settings override")

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
