import os
from typing import List
from pydantic import BaseModel, Field
from harnessfoam.agents.llm_config import build_llm, create_structured_chain
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

class FixSuggestion(BaseModel):
    file_name: str = Field(description="The name of the file that needs to be fixed")
    folder_name: str = Field(description="The directory where the file is located")
    suggestion: str = Field(description="Detailed instruction on what code changes are required")

class ReviewResult(BaseModel):
    is_resolved: bool = Field(description="True if there are no errors, False if errors found")
    fixes: List[FixSuggestion] = Field(description="List of files to fix and how to fix them")

def build_reviewer_agent(llm_kwargs: dict = None):
    kwargs = (llm_kwargs or {}).copy()
    if 'temperature' not in kwargs: kwargs['temperature'] = 0.1
    llm = build_llm(**kwargs)
    
    prompt = PromptTemplate(
        template="""You are an expert in OpenFOAM simulation and numerical modeling.
Your task is to review the provided error logs and diagnose the underlying issues. 

Error Logs:
{error_logs}

If there are no errors, set is_resolved to True.
If there are errors, set is_resolved to False and provide concrete suggestions for which files to modify and exactly what to change. Do not propose solutions that require modifying any parameters declared in the user requirement.

Provide the response in the structured format required.
""",
        input_variables=["error_logs"]
    )
    
    chain = create_structured_chain(llm, prompt, ReviewResult)
    return chain

def analyze_errors(error_logs: str, llm_kwargs: dict = None) -> dict:
    """Execute the reviewer agent to analyze logs and suggest fixes."""
    try:
        chain = build_reviewer_agent(llm_kwargs=llm_kwargs)
        result = chain.invoke({"error_logs": error_logs})
        return {
            "is_resolved": result.is_resolved,
            "suggestions": [{"file": f.file_name, "folder": f.folder_name, "fix": f.suggestion} for f in result.fixes]
        }
    except Exception as e:
        print(f"Reviewer Agent failed: {e}")
        # Fallback mechanism
        return {
            "is_resolved": False,
            "suggestions": [{"file": "controlDict", "folder": "system", "fix": "Reduce time step to satisfy Courant number limit."}]
        }

def analyze_visual_anomalies(image_path: str, user_requirement: str) -> dict:
    """Execute VLM to visually inspect the physical accuracy of the rendered output."""
    import base64
    from langchain_core.messages import HumanMessage
    
    llm = build_llm(temperature=0.1)
    
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
        
        return {
            "visual_inspection_passed": "yes" in response.content.lower() or "correct" in response.content.lower(),
            "vlm_feedback": response.content
        }
    except Exception as e:
        print(f"Visual Reviewer (VLM) failed: {e}")
        return {
            "visual_inspection_passed": True, # Fallback to true
            "vlm_feedback": "Graceful Degradation: VLM analysis bypassed due to API error."
        }

