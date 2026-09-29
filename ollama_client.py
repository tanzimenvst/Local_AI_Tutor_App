import json
import urllib.request


OLLAMA_URL = "http://localhost:11434/api/generate"


def ask_qwen(prompt: str, system_prompt: str, model: str) -> str:
    full_prompt = f"""
{system_prompt}

The learner's current message is:

{prompt}

Respond appropriately according to your tutor persona.
"""

    payload = {
        "model": model,
        "prompt": full_prompt,
        "stream": False,
    }

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    with urllib.request.urlopen(request) as response:
        result = json.loads(response.read().decode("utf-8"))

    return result["response"]

