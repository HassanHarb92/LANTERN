"""Argo OpenAI-compatible endpoint, with fail-closed networking behavior.

One of three interchangeable providers; see llm.py for the others and for the
factory that chooses between them.
"""
import os
import re
import requests
from .llm import LLMError, TRUNCATION_NOTE, default_timeout

class ArgoError(LLMError):
    """Argo-specific failure. Catching LLMError catches this too, so callers
    that want to be provider-agnostic do not have to name the gateway."""


# Argo reports a rejected credential as HTTP 200 carrying a well-formed chat
# completion whose content is an "ACCESS DENIED" notice. raise_for_status()
# cannot see it, so without the guard below the notice is rendered to the user
# as scientific analysis. Two structural signals identify it without matching
# the prose, which is free to change: the completion id is prefixed, and no
# tokens were billed.
BLOCKED_ID_PREFIX = "chatcmpl-blocked-"

_O_SERIES = re.compile(r"o\d+(-[a-z0-9]+)?$", re.IGNORECASE)

# Anthropic models on Argo reject max_tokens above this when not streaming.
ANTHROPIC_MAX_TOKENS = 21000


def sampling_params(model: str, max_tokens: int) -> dict:
    """Per-family sampling parameters.

    Argo's model families disagree about these, and sending the wrong shape is
    an error rather than a silently ignored field:
      - o-series take max_completion_tokens and no temperature;
      - GPT-5.x accept temperature only if it is exactly 1, so it is omitted;
      - Anthropic models require an explicit max_tokens, capped non-streaming.
    """
    name = (model or "").strip()
    low = name.lower()
    if _O_SERIES.match(low):
        return {"max_completion_tokens": max_tokens}
    if low.startswith("gpt-5"):
        return {"max_tokens": max_tokens}
    if low.startswith("claude"):
        return {"temperature": 0.2, "max_tokens": min(max_tokens, ANTHROPIC_MAX_TOKENS)}
    return {"temperature": 0.2, "max_tokens": max_tokens}


def reject_if_blocked(body: dict) -> None:
    """Raise when Argo refused the request but answered HTTP 200."""
    if str(body.get("id", "")).startswith(BLOCKED_ID_PREFIX):
        raise ArgoError(
            "Argo rejected the credential: it returned a blocked response. "
            "ARGO_USER must be your ANL domain username."
        )
    usage = body.get("usage") or {}
    if usage.get("total_tokens") == 0:
        raise ArgoError(
            "Argo returned a zero-token completion, which indicates a rejected "
            "credential or an unavailable model rather than an answer."
        )


class ArgoClient:
    name = "argo"
    label = "Argonne Argo"
    key_variable = "ARGO_USER"

    def __init__(self, base_url=None, user=None, model=None, timeout=None):
        self.base_url = (base_url or os.getenv("ARGO_BASE_URL", "https://apps.inside.anl.gov/argoapi/v1")).rstrip("/")
        # An ANL domain username, not a secret key. ARGO_API_KEY is the former
        # name, still read so that existing .env files keep working.
        self.user = user or os.getenv("ARGO_USER") or os.getenv("ARGO_API_KEY", "")
        self.model = model or os.getenv("ARGO_MODEL", "")
        self.timeout = timeout or default_timeout()

    def configured(self) -> bool:
        """Both settings are present. Says nothing about whether they work."""
        return bool(self.user and self.model)

    # Retained for existing callers; configured() is the clearer name.
    def ready(self):
        return self.configured()

    def health(self) -> tuple[bool, str]:
        """One network call to check the gateway answers and the model exists.

        Note this does *not* validate the username: /models is served without
        authentication. Only chat() can confirm the credential, which is why
        reject_if_blocked() exists.
        """
        if not self.configured():
            return False, "ARGO_USER and ARGO_MODEL are not both set in .env."
        try:
            r = requests.get(f"{self.base_url}/models",
                             headers={"Authorization": f"Bearer {self.user}"},
                             timeout=self.timeout)
            r.raise_for_status()
            ids = [m.get("id") for m in r.json().get("data", [])]
        except (requests.RequestException, ValueError) as exc:
            return False, f"Argo gateway unreachable ({type(exc).__name__})."
        if not ids:
            return False, "Argo returned an empty model list."
        if self.model not in ids:
            return False, f"ARGO_MODEL={self.model!r} is not among the {len(ids)} models Argo offers."
        return True, f"Gateway reachable and {self.model} is available (credential unverified until first query)."

    def chat(self, messages: list[dict], max_tokens=900) -> str:
        if not self.configured():
            raise ArgoError("Set ARGO_USER (your ANL domain username) and ARGO_MODEL in .env for live AI analysis.")
        payload = {"model": self.model, "messages": messages, "user": self.user}
        payload.update(sampling_params(self.model, max_tokens))
        try:
            r = requests.post(f"{self.base_url}/chat/completions", json=payload,
                              headers={"Authorization": f"Bearer {self.user}",
                                       "Content-Type": "application/json"},
                              timeout=self.timeout)
            r.raise_for_status()
            body = r.json()
        except (requests.RequestException, ValueError) as exc:
            raise ArgoError(f"Argo request failed: {type(exc).__name__}. Check model, access, and network.") from exc

        reject_if_blocked(body)

        try:
            choice = body["choices"][0]
            content = choice["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ArgoError("Argo returned a response with no message content.") from exc
        if not isinstance(content, str) or not content.strip():
            raise ArgoError("Argo returned an empty or non-text response.")
        # Argo is OpenAI-shaped, so it reports a clipped completion the same
        # way. Disclosing it keeps all three providers interchangeable: a
        # narration that stops mid-caveat must not read as a finished answer.
        if isinstance(choice, dict) and choice.get("finish_reason") == "length":
            content += TRUNCATION_NOTE
        return content
