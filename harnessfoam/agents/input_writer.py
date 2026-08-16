import os
import re
import requests
from typing import Dict, List
from harnessfoam.agents.llm_config import build_llm
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()


def write_simulation_inputs(
    plan: List[Dict[str, str]],
    prompt_text: str,
    case_dir: str = "",
    llm_kwargs: dict = None
) -> Dict[str, str]:
    """
    Execute the input writer agent to generate file contents.
    Uses LangChain to ensure callbacks stream to the UI.
    """
    llm_kwargs = llm_kwargs or {}
    llm = build_llm(**llm_kwargs)
    generated_files: Dict[str, str] = {}

    for item in plan:
        file_name   = item['file']
        folder_name = item['folder']
        path        = f"{folder_name}/{file_name}"
        
        full_path = ""
        if case_dir:
            full_path = os.path.join(case_dir, path.lstrip("/\\"))
            
        # Check if file already exists and is valid
        skip_generation = False
        if full_path and os.path.exists(full_path):
            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    existing_content = f.read()
                # Simple heuristic to determine if it's a valid OpenFOAM file
                if "FoamFile" in existing_content and "Mock OpenFOAM content" not in existing_content:
                    print(f"Input Writer: SKIP {path} (already exists and valid)", flush=True)
                    generated_files[path] = existing_content
                    skip_generation = True
            except Exception as e:
                print(f"Input Writer: Failed to read existing {path}: {e}")

        if skip_generation:
            continue

        # Build context from previously generated files (keep short to avoid token bloat)
        context_parts = []
        for k, v in list(generated_files.items())[-3:]:  # Only last 3 files as context
            context_parts.append(f"--- {k} ---\n{v[:500]}\n")
        context_str = "\n".join(context_parts) if context_parts else "None yet."

        user_prompt = (
            f"Generate the complete OpenFOAM '{file_name}' file for the '{folder_name}/' directory.\n\n"
            f"Simulation requirement: {prompt_text}\n\n"
            f"Previously generated files (for consistency reference):\n{context_str}\n\n"
            f"Output ONLY the raw file content. Start with the FoamFile header. Do not use Markdown formatting or code fences."
        )

        prompt = PromptTemplate(
            template="You are an expert OpenFOAM engineer. {prompt}",
            input_variables=["prompt"]
        )
        chain = prompt | llm | StrOutputParser()

        try:
            content = chain.invoke({"prompt": user_prompt})

            # Strip accidental markdown fences
            if content.startswith('```'):
                lines = content.split('\n')
                lines = [l for l in lines if not l.strip().startswith('```')]
                content = '\n'.join(lines).strip()

            # Strip <think> blocks that some models inject into content
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()

            if not content:
                raise ValueError("API returned empty content after stripping")

            generated_files[path] = content
            print(f"Input Writer: OK {path} ({len(content)} chars)", flush=True)

        except Exception as e:
            print(f"Input Writer: FAIL {path}: {e}", flush=True)
            generated_files[path] = (
                f"// Mock OpenFOAM content for {path}\n"
                f"// Requirement: {prompt_text}\n"
                f"// Error: {e}\n"
            )

    return generated_files
