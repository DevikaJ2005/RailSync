"""Turn factual simulated rule-based recommendations into concise explanations."""

import os
import time
import requests

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OLLAMA_URL = "http://localhost:11434/api/generate"
TIMEOUT_SECONDS = 3
OPENROUTER_TIMEOUT_SECONDS = int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "15"))
OLLAMA_TIMEOUT_SECONDS = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "20"))
RETRY_COOLDOWN_SECONDS = 60
SYSTEM_PROMPT = (
    "You are a railway control assistant writing for a control-room screen. "
    "Explain this recommendation in one or two very short sentences that anyone can understand. "
    "Use everyday words only. Say which train goes first and which trains wait, and give the reason "
    "in plain words (for example: the express goes first, or the other train is less delayed). "
    "Do NOT mention priority scores or compare numbers. Keep train numbers and minutes. Do not add facts."
)

_unavailable_until = {"openrouter": 0.0, "ollama": 0.0}


def narrate_decision(reason: str) -> str:
    provider = os.getenv("LLM_PROVIDER", "auto").lower()
    api_key = os.getenv("OPENROUTER_API_KEY")
    if provider == "auto":
        providers = ["openrouter", "ollama"] if api_key else ["ollama"]
    else:
        providers = [provider]

    for selected_provider in providers:
        if time.monotonic() < _unavailable_until.get(selected_provider, 0.0):
            continue
        if selected_provider == "openrouter" and api_key:
            narrated = _narrate_with_openrouter(reason, api_key)
        elif selected_provider == "ollama":
            narrated = _narrate_with_ollama(reason)
        else:
            continue
        if narrated:
            return narrated
    return reason


def _narrate_with_openrouter(reason: str, api_key: str):
    model = os.getenv("OPENROUTER_MODEL", "minimax/minimax-m3:free")

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "http://localhost:8000",
                "X-Title": "RailSync",
            },
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
                "reasoning": {"enabled": False},
            },
            timeout=OPENROUTER_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        data = response.json()
        msg = data["choices"][0]["message"]
        narrated = (msg.get("content") or "").strip()
        return narrated or None
    except Exception as e:
        _unavailable_until["openrouter"] = time.monotonic() + RETRY_COOLDOWN_SECONDS
        print(f"[llm_narration] OpenRouter unavailable ({e}); trying Ollama if enabled.")
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
            # Narration is optional and must never stall controller actions or
            # the simulation loop. A short timeout plus cooldown keeps the
            # deterministic template explanation immediately available.
            timeout=min(OLLAMA_TIMEOUT_SECONDS, 3),
        )
        response.raise_for_status()
        narrated = response.json().get("response", "").strip()
        return narrated or None
    except Exception as e:
        _unavailable_until["ollama"] = time.monotonic() + RETRY_COOLDOWN_SECONDS
        print(f"[llm_narration] Ollama unavailable ({e}); using template reason.")
        return None
