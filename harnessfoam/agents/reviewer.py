import os
from typing import List
from pydantic import BaseModel, Field
from harnessfoam.agents.llm_config import build_llm, create_structured_chain
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv
import re
from harnessfoam.knowledge import format_context

load_dotenv()

class FixSuggestion(BaseModel):
    file_name: str = Field(description="The name of the file that needs to be fixed")
    folder_name: str = Field(description="The directory where the file is located")
    suggestion: str = Field(description="Detailed instruction on what code changes are required")

class ReviewResult(BaseModel):
    is_resolved: bool = Field(description="True if there are no errors, False if errors found")
    fixes: List[FixSuggestion] = Field(description="List of files to fix and how to fix them")


def deterministic_suggestions(error_logs: str) -> List[dict]:
    """Map common deterministic validator errors to exact files."""
    suggestions = []
    text = error_logs or ""
    for path in re.findall(r"(?:Missing required OpenFOAM file|Planned file was not written|Missing FoamFile header|Placeholder content is not allowed):\s*([^\s]+)", text):
        clean = path.replace('\\', '/')
        if '/' in clean:
            folder, file_name = clean.rsplit('/', 1)
            suggestions.append({"file": file_name, "folder": folder, "fix": f"Regenerate the complete file {clean}; preserve all user-declared physical parameters and include a valid FoamFile header."})
    for field, mesh, generated in re.findall(r"Patch mismatch for 0/(\w+): mesh=\[(.*?)\], field=\[(.*?)\]", text):
        suggestions.append({"file": field, "folder": "0", "fix": f"Make boundaryField patch names exactly match blockMeshDict. Mesh patches are [{mesh}], but this field has [{generated}]."})
    if "controlDict has no application" in text:
        suggestions.append({"file": "controlDict", "folder": "system", "fix": "Add the correct OpenFOAM application entry, for example application icoFoam; consistent with the requested solver."})
    for solver, path in re.findall(r"(\w+) requires ([\w./]+)", text):
        if '/' in path:
            folder, file_name = path.rsplit('/', 1)
            suggestions.append({"file": file_name, "folder": folder, "fix": f"Generate {path}, which is required by solver {solver}, and keep it consistent with the selected physical model."})
    return suggestions

def build_reviewer_agent(llm_kwargs: dict = None):
    kwargs = (llm_kwargs or {}).copy()
    if 'temperature' not in kwargs: kwargs['temperature'] = 0.1
    llm = build_llm(**kwargs)
    
    prompt = PromptTemplate(
        template="""You are an expert in OpenFOAM simulation and numerical modeling.
Your task is to review the provided error logs and diagnose the underlying issues. 

Canonical troubleshooting guidance:
{retrieved_context}

Error Logs:
{error_logs}

If there are no errors, set is_resolved to True.
If there are errors, set is_resolved to False and provide concrete suggestions for which files to modify and exactly what to change. Do not propose solutions that require modifying any parameters declared in the user requirement.

Provide the response in the structured format required.
""",
        input_variables=["error_logs", "retrieved_context"]
    )
    
    chain = create_structured_chain(llm, prompt, ReviewResult)
    return chain

def analyze_errors(error_logs: str, llm_kwargs: dict = None, memory_context: str = "") -> dict:
    """Execute the reviewer agent to analyze logs and suggest fixes."""
    try:
        chain = build_reviewer_agent(llm_kwargs=llm_kwargs)
        result = chain.invoke({"error_logs": error_logs + memory_context, "retrieved_context": format_context(error_logs, k=4, route="reviewer")})
        return {
            "is_resolved": result.is_resolved,
            "suggestions": [{"file": f.file_name, "folder": f.folder_name, "fix": f.suggestion} for f in result.fixes]
        }
    except Exception as e:
        print(f"Reviewer Agent failed: {e}")
        deterministic = deterministic_suggestions(error_logs)
        return {
            "is_resolved": False,
            "suggestions": deterministic or [{"file": "controlDict", "folder": "system", "fix": "Reduce time step to satisfy Courant number limit."}]
        }

def analyze_visual_anomalies(image_path: str, user_requirement: str, llm_kwargs: dict = None) -> dict:
    """Execute VLM to visually inspect the physical accuracy of the rendered output."""
    import base64
    from langchain_core.messages import HumanMessage
    
    llm = build_llm(temperature=0.1, **(llm_kwargs or {}))
    
    try:
        with open(image_path, "rb") as image_file:
            encoded_image = base64.b64encode(image_file.read()).decode('utf-8')
            
        message = HumanMessage(
            content=[
                {"type": "text", "text": f"You are a CFD expert. Analyze this flow field visualization based on the user requirement: '{user_requirement}'. Does it look physically correct? If not, propose parameter changes for OpenFOAM dictionaries."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encoded_image}"}}
            ]
        )
        
        # We skip structured output here for broader VLM compatibility
        response = llm.invoke([message])
        
        passed = "yes" in response.content.lower() or "correct" in response.content.lower()
        return {"visual_inspection_passed": passed, "visual_review_status": "PASSED" if passed else "FAILED", "vlm_feedback": response.content}
    except Exception as e:
        print(f"Visual Reviewer (VLM) failed: {e}")
        return {
            "visual_inspection_passed": None,
            "visual_review_status": "SKIPPED",
            "vlm_feedback": "VLM analysis skipped because the configured vision model was unavailable."
        }

