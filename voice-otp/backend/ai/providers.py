import json

import requests

from ai.config import (
    OLLAMA_GENERATE_URL,
    OLLAMA_MODEL,
    OLLAMA_NUM_PREDICT,
    OLLAMA_TAGS_URL,
    OLLAMA_TIMEOUT_ASK,
    OLLAMA_TIMEOUT_DASHBOARD,
)


class AIProvider:
    name = "base"
    model = None

    def complete(self, system_prompt, user_prompt, timeout=None, json_mode=False):
        raise NotImplementedError


class LocalAIProvider(AIProvider):
    name = "ollama"
    model = OLLAMA_MODEL

    def complete(self, system_prompt, user_prompt, timeout=None, json_mode=False):
        prompt = f"{system_prompt.strip()}\n\n{user_prompt.strip()}"
        body = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "num_predict": OLLAMA_NUM_PREDICT,
            },
        }
        if json_mode:
            body["format"] = "json"
        resp = requests.post(
            OLLAMA_GENERATE_URL,
            json=body,
            timeout=timeout or OLLAMA_TIMEOUT_ASK,
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"ollama_http_{resp.status_code}: {resp.text[:300]}")
        data = resp.json()
        text = data.get("response") or (data.get("message") or {}).get("content") or ""
        return (text or "").strip()


class TemplateAIProvider(AIProvider):
    name = "template"
    model = None

    def complete(self, system_prompt, user_prompt, timeout=None, json_mode=False):
        return ""


def ollama_status():
    try:
        ping = requests.get(OLLAMA_TAGS_URL, timeout=3)
        if ping.status_code != 200:
            return {"online": False, "model": OLLAMA_MODEL, "models": [], "model_ready": False}
        names = [item.get("name") for item in (ping.json().get("models") or []) if item.get("name")]
        return {
            "online": True,
            "model": OLLAMA_MODEL,
            "model_ready": any(
                OLLAMA_MODEL in (name or "") or (name or "").startswith("llama3.2")
                for name in names
            ),
            "models": names,
        }
    except Exception:
        return {"online": False, "model": OLLAMA_MODEL, "models": [], "model_ready": False}


def get_provider():
    status = ollama_status()
    if status.get("online") and status.get("model_ready"):
        return LocalAIProvider()
    return TemplateAIProvider()


def ask_llm(system_prompt, user_prompt, context, timeout=None, json_mode=False):
    provider = get_provider()
    payload = (
        user_prompt
        + "\n\nCONTEXT (JSON, only source of truth):\n"
        + json.dumps(context, ensure_ascii=False)
    )
    try:
        text = provider.complete(
            system_prompt,
            payload,
            timeout=timeout or OLLAMA_TIMEOUT_ASK,
            json_mode=json_mode,
        )
        return text, provider.name, provider.model
    except Exception as exc:
        print(f"[AI] LLM call failed: {type(exc).__name__}: {exc}")
        return "", "template", None


def ask_llm_json(system_prompt, user_prompt, context, timeout=None):
    text, name, model = ask_llm(
        system_prompt,
        user_prompt,
        context,
        timeout=timeout or OLLAMA_TIMEOUT_DASHBOARD,
        json_mode=True,
    )
    parsed = _parse_json(text)
    if parsed is None and text:
        text2, name2, model2 = ask_llm(
            system_prompt,
            user_prompt,
            context,
            timeout=timeout or OLLAMA_TIMEOUT_DASHBOARD,
            json_mode=False,
        )
        parsed = _parse_json(text2) or _parse_labeled(text2)
        if parsed:
            return parsed, name2, model2
    return parsed, name, model


def _parse_json(text):
    blob = (text or "").strip()
    if not blob:
        return None
    if blob.startswith("```"):
        blob = blob.strip("`")
        if blob.lower().startswith("json"):
            blob = blob[4:]
        blob = blob.strip()
    try:
        data = json.loads(blob)
        return data if isinstance(data, dict) else None
    except Exception:
        start = blob.find("{")
        end = blob.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(blob[start:end + 1])
                return data if isinstance(data, dict) else None
            except Exception:
                return None
        return None


def _parse_labeled(text):
    lines = [line.strip() for line in (text or "").splitlines() if line.strip()]
    if not lines:
        return None
    data = {"analysis": "", "recommendations": []}
    current = None
    chunks = []
    for line in lines:
        key = line.split(":", 1)[0].strip().lower()
        value = line.split(":", 1)[1].strip() if ":" in line else line
        if key in ("headline", "titre"):
            data["headline"] = value
            current = None
        elif key in ("analysis", "analyse"):
            current = "analysis"
            chunks = [value] if value else []
        elif key in ("issue", "main_issue", "probleme", "problème"):
            data["main_issue"] = value
            current = None
        elif key.startswith("rec") or key in ("recommendations", "recommandations"):
            current = "recommendations"
            if value.startswith("-"):
                value = value[1:].strip()
            if value:
                data["recommendations"].append(value)
        elif current == "analysis":
            chunks.append(line)
        elif current == "recommendations" and line.startswith("-"):
            data["recommendations"].append(line[1:].strip())
    if chunks:
        data["analysis"] = " ".join(chunks).strip()
    if data.get("analysis"):
        return data
    return None
