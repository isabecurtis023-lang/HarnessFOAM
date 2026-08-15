import os
from typing import Dict, List
from pydantic import BaseModel, Field
from harnessfoam.agents.llm_config import build_llm
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

class FileContentResult(BaseModel):
    content: str = Field(description="The complete and functional OpenFOAM file content")

def build_input_writer_agent():
    llm = build_llm(temperature=0.1)
    
    prompt = PromptTemplate(
        template="""You are an expert in OpenFOAM simulation and numerical modeling. 
Your task is to generate a complete and functional file named: {file_name} within the {folder_name} directory. 

User requirement: {user_requirement}
Previously generated files context (for reference):
{context}

Ensure all required values are present. Provide ONLY the code content in your response, with no explanations or comments.
""",
        input_variables=["file_name", "folder_name", "user_requirement", "context"]
    )
    
    chain = prompt | llm.with_structured_output(FileContentResult)
    return chain

# 2026-08-15 | Gemini 3.5 Flash (Medium)
def write_simulation_inputs(plan: List[Dict[str, str]], prompt_text: str) -> Dict[str, str]:
    """Execute the input writer agent to generate file contents."""
    generated_files = {}
    
    for item in plan:
        file_name = item['file']
        folder_name = item['folder']
        path = f"{folder_name}/{file_name}"
        
        # Build context from previously generated files
        context_str = "\n".join([f"--- {k} ---\n{v}\n" for k, v in generated_files.items()])
        
        try:
            chain = build_input_writer_agent()
            result = chain.invoke({
                "file_name": file_name,
                "folder_name": folder_name,
                "user_requirement": prompt_text,
                "context": context_str
            })
            generated_files[path] = result.content
        except Exception as e:
            print(f"Input Writer Agent failed for {path}: {e}")
            # Fallback to dummy data
            generated_files[path] = f"// Mock OpenFOAM content for {path}\n// Requirement: {prompt_text}"
            
    return generated_files
