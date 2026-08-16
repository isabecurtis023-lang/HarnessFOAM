"""LLM usage and optional cost accounting."""
import os
from typing import Dict


def estimate_cost(usage: Dict[str, object], model: str = "") -> Dict[str, object]:
    prompt = usage.get("prompt_tokens")
    completion = usage.get("completion_tokens")
    input_rate = float(os.getenv("LLM_INPUT_USD_PER_1M", "0") or 0)
    output_rate = float(os.getenv("LLM_OUTPUT_USD_PER_1M", "0") or 0)
    cost = None
    if isinstance(prompt, (int, float)) and isinstance(completion, (int, float)) and (input_rate or output_rate):
        cost = (float(prompt) / 1_000_000 * input_rate) + (float(completion) / 1_000_000 * output_rate)
    return {"model": model, "prompt_tokens": prompt, "completion_tokens": completion, "total_tokens": (prompt + completion if isinstance(prompt, (int, float)) and isinstance(completion, (int, float)) else None), "estimated_cost_usd": cost, "cost_status": "CALCULATED" if cost is not None else "UNPRICED"}
