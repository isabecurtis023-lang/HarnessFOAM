import os
from pydantic import BaseModel, Field
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

class VisualizationScriptResult(BaseModel):
    is_visualization_required: bool = Field(description="True if the user requested any visualization, False otherwise.")
    pyvista_script: str = Field(description="The complete python script using pyvista to render the flow field and save as .png. Empty if not required.")

def build_visualizer_agent():
    llm = ChatOpenAI(
        model="DeepSeek-V3.2",
        temperature=0.1
    )
    
    prompt = PromptTemplate(
        template="""You are an expert in scientific data visualization using PyVista.
Analyze the user requirement. If the user requests to visualize a field (e.g. 'Visualize the magnitude of velocity'), set is_visualization_required to True and write a Python script using the `pyvista` library to read OpenFOAM VTK data and render the specified field, saving it to 'visualization.png'.
If no visualization is requested, set is_visualization_required to False.

User requirement: {user_requirement}

Output ONLY the structured JSON. Do not provide explanations.
""",
        input_variables=["user_requirement"]
    )
    
    chain = prompt | llm.with_structured_output(VisualizationScriptResult)
    return chain

def generate_visualization_script(prompt_text: str) -> dict:
    """Execute the visualization agent to determine rendering needs and generate scripts."""
    chain = build_visualizer_agent()
    try:
        result = chain.invoke({"user_requirement": prompt_text})
        return {
            "is_visualization_required": result.is_visualization_required,
            "pyvista_script": result.pyvista_script
        }
    except Exception as e:
        print(f"Visualizer Agent failed: {e}")
        # Fallback mechanism
        return {
            "is_visualization_required": False,
            "pyvista_script": ""
        }
