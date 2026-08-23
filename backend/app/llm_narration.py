"""Turn factual ML decisions into short, simple-English Gemma explanations."""

import os
import requests

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OLLAMA_URL = "http://localhost:11434/api/generate"
TIMEOUT_SECONDS = 3
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "20"))
SYSTEM_PROMPT = (
    "You are a railway control assistant. Explain the following ML recommendation "
    "in one short sentence using very simple English. Keep every train number, "
    "score, delay, and action. Do not add facts or use technical jargon."
)


def narrate_decision(reason: str) -> str:
    provider = os.getenv("LLM_PROVIDER", "auto").lower()
    api_key = os.getenv("GROQ_API_KEY")
    if provider == "auto":
        providers = ["groq"] if api_key else []
    else:
        providers = [provider]

    for selected_provider in providers:
        if selected_provider == "groq" and api_key:
            narrated = _narrate_with_groq(reason, api_key)
        elif selected_provider == "ollama":
            narrated = _narrate_with_ollama(reason)
        else:
            continue
        if narrated:
            return narrated
    return reason


def _narrate_with_groq(reason: str, api_key: str):
    model = os.getenv("GROQ_MODEL", "gemma2-9b-it")

    try:
        response = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {"role": "user", "content": reason},
                ],
                "max_tokens": 120,
                "temperature": 0.3,
            },
            timeout=TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        narrated = data["choices"][0]["message"]["content"].strip()
        return narrated or None
    except Exception as e:
        print(f"[llm_narration] Groq unavailable ({e}); trying Ollama if enabled.")
        return None


def _narrate_with_ollama(reason: str):
    try:
        response = requests.post(
            os.getenv("OLLAMA_URL", OLLAMA_URL),
            json={
                "model": os.getenv("OLLAMA_MODEL", "gemma3:4b"),
                "prompt": f"{SYSTEM_PROMPT}\n\nRecommendation: {reason}",
                "stream": False,
                "options": {"temperature": 0.3},
            },
            timeout=OLLAMA_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        narrated = response.json().get("response", "").strip()
        return narrated or None
    except Exception as e:
        print(f"[llm_narration] Ollama unavailable ({e}); using template reason.")
        return None
