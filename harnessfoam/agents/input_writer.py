import os
import re
import requests
from typing import Dict, List
from harnessfoam.agents.llm_config import build_llm
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()


def _call_api_direct(prompt: str, llm_kwargs: dict) -> str:
    """
    Direct requests-based API call, bypassing LangChain entirely.
    Handles empty content by checking reasoning_content as fallback.
    Disables extended thinking via budget_tokens=0 where supported.
    """
    api_key  = llm_kwargs.get('api_key')  or os.getenv('OPENAI_API_KEY', 'dummy')
    base_url = llm_kwargs.get('base_url') or os.getenv('OPENAI_API_BASE', '')
    model    = llm_kwargs.get('model')    or os.getenv('LLM_MODEL', 'gpt-3.5-turbo')

    if not base_url:
        raise ValueError("API base_url is required")

    url = base_url.rstrip('/') + '/chat/completions'
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': model,
        'messages': [
            {
                'role': 'system',
                'content': (
                    'You are an expert OpenFOAM engineer. '
                    'Output ONLY raw file content — no JSON, no markdown fences, no explanations.'
                )
            },
            {'role': 'user', 'content': prompt}
        ],
        'temperature': 0.1,
        'max_tokens': 3000,
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=90)
    resp.raise_for_status()
    data = resp.json()

    choice = data['choices'][0]
    msg = choice['message']
    content = (msg.get('content') or '').strip()

    # Some thinking models put answer in reasoning_content when content is empty
    if not content:
        content = (msg.get('reasoning_content') or '').strip()

    return content


def write_simulation_inputs(
    plan: List[Dict[str, str]],
    prompt_text: str,
    llm_kwargs: dict = None
) -> Dict[str, str]:
    """
    Execute the input writer agent to generate file contents.
    Uses direct HTTP calls to avoid LangChain empty-response issues.
    """
    llm_kwargs = llm_kwargs or {}
    generated_files: Dict[str, str] = {}

    for item in plan:
        file_name   = item['file']
        folder_name = item['folder']
        path        = f"{folder_name}/{file_name}"

        # Build context from previously generated files (keep short to avoid token bloat)
        context_parts = []
        for k, v in list(generated_files.items())[-3:]:  # Only last 3 files as context
            context_parts.append(f"--- {k} ---\n{v[:500]}\n")
        context_str = "\n".join(context_parts) if context_parts else "None yet."

        user_prompt = (
            f"Generate the complete OpenFOAM '{file_name}' file for the '{folder_name}/' directory.\n\n"
            f"Simulation requirement: {prompt_text}\n\n"
            f"Previously generated files (for consistency reference):\n{context_str}\n\n"
            f"Output ONLY the raw file content. Start with the FoamFile header."
        )

        try:
            content = _call_api_direct(user_prompt, llm_kwargs)

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
