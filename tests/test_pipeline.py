import asyncio
from harnessfoam.agents.reviewer import analyze_errors
from harnessfoam.agents.input_writer import write_simulation_inputs

error_logs = """
--> FOAM FATAL IO ERROR: 
Cannot find patchField entry for movingWall
file: /mnt/c/Users/Administrator/Desktop/temp/TEST/0/U.boundaryField from line 26 to line 35.
"""

print("Running reviewer...")
rev = analyze_errors(error_logs, llm_kwargs={"temperature": 0.1})
print("Reviewer output:", rev)

print("Running input writer with suggestions...")
plan = [{"file": "U", "folder": "0"}]
prompt = "Simulate lid driven cavity."
res = write_simulation_inputs(plan, prompt, case_dir="", llm_kwargs={"temperature": 0.1}, review_suggestions=rev["suggestions"])
print("Input Writer Output:")
for path, content in res.items():
    print(f"--- {path} ---")
    print(content)
