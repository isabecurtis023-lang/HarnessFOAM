import os
import re
import requests
from typing import Dict, List
from harnessfoam.agents.llm_config import build_llm
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
from harnessfoam.cases.cavity import cavity_files, is_cavity_prompt
from harnessfoam.knowledge import format_context

load_dotenv()


def write_simulation_inputs(
    plan: List[Dict[str, str]],
    prompt_text: str,
    case_dir: str = "",
    llm_kwargs: dict = None,
    review_suggestions: List[Dict[str, str]] = None
) -> Dict[str, str]:
    """
    Execute the input writer agent to generate file contents.
    Uses LangChain to ensure callbacks stream to the UI.
    """
    llm_kwargs = llm_kwargs or {}
    llm = build_llm(**llm_kwargs)
    generated_files: Dict[str, str] = {}
    review_suggestions = review_suggestions or []
    retrieved_context = format_context(prompt_text, k=5)

    for item in plan:
        file_name   = item['file']
        folder_name = item['folder']
        path        = f"{folder_name}/{file_name}"
        
        full_path = ""
        if case_dir:
            full_path = os.path.join(case_dir, path.lstrip("/\\"))
            
        # Check if there's a specific fix instruction for this file
        specific_suggestion = ""
        for sugg in review_suggestions:
            sugg_file = sugg.get("file", "")
            sugg_folder = sugg.get("folder", "")
            
            # Clean up OpenFOAM specific sub-dictionary notation (e.g., 0/U.boundaryField -> 0/U)
            if ".boundaryField" in sugg_file: sugg_file = sugg_file.replace(".boundaryField", "")
            if ".internalField" in sugg_file: sugg_file = sugg_file.replace(".internalField", "")
            
            # Match if the file name matches exactly, OR if the file name in suggestion includes the folder (e.g. "0/U")
            # OR if it's just "U" and the plan is checking "U"
            if (sugg_file == file_name) or (sugg_file == f"{folder_name}/{file_name}") or (sugg_file == file_name and sugg_folder == folder_name) or (sugg_file.endswith(f"/{file_name}")):
                specific_suggestion = sugg.get("fix", "")
                break
                
        # Check if file already exists and is valid
        skip_generation = False
        if not specific_suggestion and full_path and os.path.exists(full_path):
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

        suggestion_text = f"CRITICAL REVISION INSTRUCTION: The previous version of this file caused an error. You MUST fix it according to this reviewer instruction: {specific_suggestion}\n\n" if specific_suggestion else ""

        user_prompt = (
            f"Generate the complete OpenFOAM '{file_name}' file for the '{folder_name}/' directory.\n\n"
            f"CRITICAL RULE: If generating 'controlDict', you MUST set 'purgeWrite 1;' to save disk space.\n\n"
            f"Simulation requirement: {prompt_text}\n\n"
            f"Canonical OpenFOAM guidance retrieved for this case:\n{retrieved_context}\n\n"
            f"{suggestion_text}"
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
            if is_cavity_prompt(prompt_text) and path in cavity_files():
                generated_files[path] = cavity_files()[path]
                print(f"Input Writer: FALLBACK {path} after LLM error: {e}", flush=True)
            else:
                raise RuntimeError(f"LLM failed while generating {path}: {e}") from e

    return generated_files
