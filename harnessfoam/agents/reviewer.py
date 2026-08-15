import os
from typing import List
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
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

def build_reviewer_agent():
    llm = ChatOpenAI(
        model="DeepSeek-V3.2",
        temperature=0.0
    )
    
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
    
    chain = prompt | llm.with_structured_output(ReviewResult)
    return chain

def analyze_errors(error_logs: str) -> dict:
    """Execute the reviewer agent to analyze logs and suggest fixes."""
    chain = build_reviewer_agent()
    try:
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
