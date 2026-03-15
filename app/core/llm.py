# app/core/llm.py
import os, re, json
from typing import Optional, Dict, Any
from openai import OpenAI
from app.core.config import OPENAI_API_KEY, OPENAI_MODEL

def _client() -> OpenAI:
    key = OPENAI_API_KEY
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    return OpenAI(api_key=key)

def _extract_json(s: str) -> Optional[Dict[str, Any]]:
    m = re.search(r"\{.*\}", s, flags=re.S)
    if not m: return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None

def chat_json(system_prompt: str, user_prompt: str, max_tokens: int = 280, model: Optional[str] = None) -> Dict[str, Any]:
    model = OPENAI_MODEL
    cli = _client()
    def call(sp, up):
        r = cli.chat.completions.create(
            model=model, temperature=0, max_tokens=max_tokens,
            messages=[{"role":"system","content":sp},{"role":"user","content":up}]
        )
        return r.choices[0].message.content or ""
    txt = call(system_prompt, user_prompt)
    data = _extract_json(txt)
    if data is not None: return data
    txt2 = call(system_prompt + "\nReturn STRICT JSON only. No prose, no markdown.", user_prompt)
    return _extract_json(txt2) or {"error": "parse_failed"}
