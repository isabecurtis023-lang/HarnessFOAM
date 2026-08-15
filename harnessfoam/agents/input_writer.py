import os
import re
import requests
from typing import Dict, List
from harnessfoam.agents.llm_config import build_llm
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv

load_dotenv()


def _call_api_direct(prompt: str, llm_kwargs: dict, max_retries: int = 2) -> str:
    """
    Direct requests-based API call using **streaming** to avoid read-timeout
    on slow / thinking models (e.g. DeepSeek-R1 on 科技云).
    Handles empty content by checking reasoning_content as fallback.
    Includes retry logic for transient network errors.
    # 2026-08-15 – Claude Opus 4.6 (Thinking): switched to streaming + retry
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
        'stream': True,          # ← stream to prevent read-timeout
    }

    import json as _json

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            # Use a long read-timeout (600s) but streaming keeps the conn alive
            resp = requests.post(
                url, headers=headers, json=payload,
                timeout=(30, 600),   # (connect, read)
                stream=True,
            )
            resp.raise_for_status()

            # ---- Collect streamed SSE chunks ----
            collected_content = []
            collected_reasoning = []

            for raw_line in resp.iter_lines(decode_unicode=True):
                if not raw_line:
                    continue
                line = raw_line.strip()
                if not line.startswith('data:'):
                    continue
                data_str = line[len('data:'):].strip()
                if data_str == '[DONE]':
                    break
                try:
                    chunk = _json.loads(data_str)
                    delta = chunk.get('choices', [{}])[0].get('delta', {})
                    if delta.get('content'):
                        collected_content.append(delta['content'])
                    if delta.get('reasoning_content'):
                        collected_reasoning.append(delta['reasoning_content'])
                except (_json.JSONDecodeError, IndexError, KeyError):
                    continue

            content = ''.join(collected_content).strip()

            # Fallback: some thinking models put answer in reasoning_content
            if not content:
                content = ''.join(collected_reasoning).strip()

            if content:
                return content

            # If both are empty, treat as transient and retry
            last_error = ValueError("API returned empty content from stream")
            print(f"Input Writer: empty stream response (attempt {attempt+1}/{max_retries+1})")

        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.ChunkedEncodingError) as e:
            last_error = e
            wait = 5 * (attempt + 1)
            print(f"Input Writer: network error (attempt {attempt+1}/{max_retries+1}): {e}, retrying in {wait}s...")
            import time
            time.sleep(wait)
        except requests.exceptions.HTTPError as e:
            # Don't retry 4xx errors (bad request, auth, etc.)
            if resp.status_code < 500:
                raise
            last_error = e
            wait = 5 * (attempt + 1)
            print(f"Input Writer: server error {resp.status_code} (attempt {attempt+1}/{max_retries+1}), retrying in {wait}s...")
            import time
            time.sleep(wait)

    raise last_error or RuntimeError("All retries exhausted")


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
