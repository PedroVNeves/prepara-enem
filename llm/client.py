"""Wrapper único do cliente Gemini — reusado pela classificação de questões
(cold-start de TRI), correção de redação e geração de temas. Centraliza
autenticação, retry e parsing de JSON para não duplicar essa lógica em cada
management command que chama a IA."""

import json
import time

from django.conf import settings
from google import genai

_client = None


class GeminiError(Exception):
    pass


def get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=settings.GEMINI_API_KEY)
    return _client


def generate_json(prompt, model=None, max_retries=3, backoff_seconds=2):
    """Chama o Gemini em JSON mode e retorna o dict já parseado.
    Retry com backoff para lidar com rate limit / instabilidade de rede."""
    model = model or settings.GEMINI_MODEL_FLASH
    client = get_client()
    last_error = None
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            return json.loads(response.text)
        except Exception as exc:  # rate limit, JSON malformado, timeout, etc.
            last_error = exc
            if attempt < max_retries - 1:
                time.sleep(backoff_seconds * (attempt + 1))
    raise GeminiError(
        f"Falha ao gerar JSON via Gemini após {max_retries} tentativas: {last_error}"
    )


def generate_text(prompt, model=None):
    model = model or settings.GEMINI_MODEL_FLASH
    client = get_client()
    response = client.models.generate_content(model=model, contents=prompt)
    return response.text
