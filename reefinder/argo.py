"""Argo OpenAI-compatible endpoint, with fail-closed networking behavior."""
import os
import requests

class ArgoError(RuntimeError):
    pass

class ArgoClient:
    def __init__(self, base_url=None, api_key=None, model=None, timeout=25):
        self.base_url = (base_url or os.getenv("ARGO_BASE_URL", "https://apps.inside.anl.gov/argoapi/v1")).rstrip("/")
        self.api_key = api_key or os.getenv("ARGO_API_KEY", "")
        self.model = model or os.getenv("ARGO_MODEL", "")
        self.timeout = timeout

    def ready(self):
        return bool(self.api_key and self.model)

    def chat(self, messages: list[dict], max_tokens=900) -> str:
        if not self.ready():
            raise ArgoError("Set ARGO_API_KEY and ARGO_MODEL in .env for live AI analysis.")
        try:
            r = requests.post(f"{self.base_url}/chat/completions", json={
                "model": self.model, "messages": messages, "temperature": 0.2, "max_tokens": max_tokens,
            }, headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                              timeout=self.timeout)
            r.raise_for_status()
            content = r.json()["choices"][0]["message"]["content"]
            if not isinstance(content, str):
                raise ArgoError("Argo returned non-text response")
            return content
        except (requests.RequestException, KeyError, IndexError, ValueError) as exc:
            raise ArgoError(f"Argo request failed: {type(exc).__name__}. Check model, access, and network.") from exc
