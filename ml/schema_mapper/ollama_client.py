"""Client API pour la communication avec l'instance Ollama locale."""

from __future__ import annotations

import json
import os
import requests

OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
DEFAULT_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")


def health_check() -> bool:
    """Vérifie qu'Ollama répond avant d'envoyer un prompt."""
    try:
        r = requests.get(OLLAMA_URL.replace("/api/generate", "/api/tags"), timeout=5)
        return r.status_code == 200
    except Exception:
        return False


def ask_json(prompt: str, model: str = DEFAULT_MODEL, temperature: float = 0.1) -> dict:
    if not health_check():
        raise RuntimeError("Ollama ne répond pas sur " + OLLAMA_URL)

    response = requests.post(
        OLLAMA_URL,
        json={
            "model": model,
            "prompt": prompt,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": 2048,  # Réduit l'empreinte mémoire RAM du modèle 8B sur CPU
            },
        },
        timeout=300,  # Laisse jusqu'à 5 minutes au modèle 8B pour répondre
    )
    response.raise_for_status()
    raw_text = response.json()["response"]

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Ollama n'a pas renvoyé un JSON valide. Réponse brute :\n{raw_text}"
        ) from exc