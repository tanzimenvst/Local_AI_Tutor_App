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


def ask_ollama_raw(prompt: str, model: str = "qwen3:8b", expect_json: bool = False) -> str:
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }
    
    if expect_json:
        payload["format"] = "json"

    data = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(
        OLLAMA_URL,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request) as response:
            result = json.loads(response.read().decode("utf-8"))
        return result.get("response", "")
    except Exception as e:
        print(f"Error querying Ollama raw: {e}")
        return ""

def get_available_models() -> list:
    url = "http://localhost:11434/api/tags"
    try:
        with urllib.request.urlopen(url) as response:
            result = json.loads(response.read().decode("utf-8"))
            return [model["name"] for model in result.get("models", [])]
    except Exception as e:
        print(f"Error fetching Ollama models: {e}")
        return ["qwen3:8b", "llama3:8b", "mistral"]
