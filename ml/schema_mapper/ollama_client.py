"""Client API pour la communication avec l'instance Ollama locale."""

from __future__ import annotations

import json
import requests

OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.1:8b"


def ask_json(prompt: str, model: str = DEFAULT_MODEL, temperature: float = 0.1) -> dict:
    """Envoie un prompt à Ollama et retourne la réponse sous forme de dictionnaire JSON."""
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {"temperature": temperature},
        },
        timeout=120,
    )
    response.raise_for_status()
    raw_text = response.json()["response"]

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Ollama n'a pas renvoyé un JSON valide. Réponse brute :\n{raw_text}"
        ) from exc