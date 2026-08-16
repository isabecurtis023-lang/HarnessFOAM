import os
from pydantic import BaseModel, Field
from harnessfoam.agents.llm_config import build_llm, create_structured_chain
from langchain_core.prompts import PromptTemplate
from dotenv import load_dotenv

load_dotenv()

class VisualizationScriptResult(BaseModel):
    is_visualization_required: bool = Field(description="True if the user requested any visualization, False otherwise.")
    pyvista_script: str = Field(description="The complete python script using pyvista to render the flow field and save as .png. Empty if not required.")

def build_visualizer_agent(llm_kwargs: dict = None):
    kwargs = (llm_kwargs or {}).copy()
    if 'temperature' not in kwargs: kwargs['temperature'] = 0.1
    llm = build_llm(**kwargs)
    
    prompt = PromptTemplate(
        template="""You are an expert in scientific data visualization using PyVista.
Analyze the user requirement. You MUST ALWAYS write a Python script using the `pyvista` library to read OpenFOAM VTK data and render the specified field, saving it to 'visualization.png'.
If the user does not explicitly specify what to visualize, default to visualizing the velocity magnitude (U).
Set is_visualization_required to True always, unless the user explicitly commands you not to visualize anything.

CRITICAL PYVISTA INSTRUCTION:
Do NOT use `pv.OpenFOAMReader(".")` or pass a directory name to the reader, as this causes an AttributeError in older VTK versions.
Instead, you MUST create an empty file named `case.foam` in the current directory and pass it to the reader using `pv.OpenFOAMReader("case.foam")`.
Furthermore, you MUST use `off_screen=True` in the plotter to prevent the script from hanging in a headless environment.
CRITICAL OPENFOAM MULTIBLOCK INSTRUCTION:
The `reader.read()` method returns a `pyvista.MultiBlock` dataset. OpenFOAM fields like 'U' or 'p' are NOT block names, they are array scalars inside the blocks (typically inside the `internalMesh` block).
Do NOT attempt to extract arrays via `mesh['U']`. Do NOT iterate over the blocks. Do NOT use `block.array_names`.
Instead, pass the multiblock mesh DIRECTLY to the plotter and specify the scalar name: `plotter.add_mesh(mesh, scalars='U')`.
NOTE: PyVista automatically computes the magnitude of vector fields like 'U' when you pass `scalars='U'`. You DO NOT need to extract vector components or compute the magnitude yourself.
For example:
```python
import pyvista as pv
with open("case.foam", "w") as f: pass
reader = pv.OpenFOAMReader("case.foam")
reader.set_active_time_value(reader.time_values[-1])
mesh = reader.read()
plotter = pv.Plotter(off_screen=True)
plotter.add_mesh(mesh, scalars='U')
plotter.screenshot('visualization.png')
plotter.close()
```

User requirement: {user_requirement}

Output ONLY the structured JSON. Do not provide explanations.
""",
        input_variables=["user_requirement"]
    )
    
    chain = create_structured_chain(llm, prompt, VisualizationScriptResult)
    return chain

def generate_visualization_script(prompt_text: str, llm_kwargs: dict = None, memory_context: str = "") -> dict:
    """Execute the visualization agent to determine rendering needs and generate scripts."""
    try:
        chain = build_visualizer_agent(llm_kwargs=llm_kwargs)
        result = chain.invoke({"user_requirement": prompt_text + memory_context})
        return {
            "is_gmsh_required": result.is_visualization_required, # Note: using is_gmsh_required in parent graph returned dict for backward compat
            "is_visualization_required": result.is_visualization_required,
            "pyvista_script": result.pyvista_script
        }
    except Exception as e:
        print(f"Visualizer Agent failed, using default post-processing script: {e}")
        # Deep Driving must remain useful when the model is unavailable.  This
        # is a real post-processing script, never a placeholder response.
        return {
            "is_visualization_required": True,
            "pyvista_script": '''import pyvista as pv
with open("case.foam", "a", encoding="utf-8"):
    pass
reader = pv.OpenFOAMReader("case.foam")
if reader.time_values:
    reader.set_active_time_value(reader.time_values[-1])
mesh = reader.read()
plotter = pv.Plotter(off_screen=True)
plotter.add_mesh(mesh, scalars="U", show_edges=False)
plotter.view_xy()
plotter.screenshot("visualization.png")
plotter.close()
'''
        }
import subprocess
import base64
import sys

def execute_visualization(case_dir: str, pyvista_script: str) -> str:
    """Executes the PyVista script and returns the resulting image as base64."""
    if not pyvista_script:
        return ""
        
    script_path = os.path.join(case_dir, "viz_postprocess.py")
    img_path = os.path.join(case_dir, "visualization.png")
    
    with open(script_path, "w") as f:
        f.write(pyvista_script)
        
    try:
        import shutil
        # On Windows, `python3` may resolve to the Microsoft Store alias and
        # use a different environment from the application.  Always reuse the
        # interpreter running HarnessFOAM there.
        python_exe = sys.executable if os.name == "nt" else (shutil.which("python3") or sys.executable)
        
        # In a real environment, this would run `python viz_postprocess.py`
        # PyVista in headless Linux (like WSL) usually requires xvfb
        if shutil.which("xvfb-run") and os.name == "posix":
            subprocess.run(["xvfb-run", "-a", python_exe, "viz_postprocess.py"], cwd=case_dir, check=True)
        else:
            subprocess.run([python_exe, "viz_postprocess.py"], cwd=case_dir, check=True)
        
        if os.path.exists(img_path):
            with open(img_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
    except Exception as e:
        print(f"Failed to execute visualization: {e}")
    return ""
