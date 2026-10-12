import json
import re

import google.generativeai as genai
from fastapi import HTTPException

from . import config

_configured = False


def generate_json(prompt: str):
    """Send a prompt to Gemini and parse the JSON response."""
    global _configured
    config.require_gemini()
    if not _configured:
        genai.configure(api_key=config.GEMINI_API_KEY)
        _configured = True

    model = genai.GenerativeModel(
        config.GEMINI_MODEL,
        generation_config={"response_mime_type": "application/json"},
    )
    try:
        response = model.generate_content(prompt)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Gemini request failed: {exc}")

    if not response.candidates or not response.candidates[0].content.parts:
        raise HTTPException(
            status_code=502, detail="Gemini returned an empty response. Check your API key quota."
        )
    return parse_json(response.text)


def parse_json(raw: str):
    """Parse JSON, falling back to the first array/object embedded in the text."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    match = re.search(r"(\[.*\]|\{.*\})", raw, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    raise HTTPException(status_code=502, detail="Could not parse the Gemini response as JSON.")
