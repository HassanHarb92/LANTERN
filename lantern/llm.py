"""Provider-agnostic chat layer: Argonne Argo, OpenAI, or Anthropic.

WHY THREE CLIENTS AND NOT ONE ADAPTER. Argo and OpenAI speak the same wire
format, so sharing code between them is free. Anthropic does not, and the
difference is not cosmetic:

  - the system prompt is a **top-level `system` parameter**, and the Messages
    API documents that there is no `"system"` role for input messages. A client
    that forwards `[{"role": "system", ...}]` unchanged has its instructions
    either rejected or silently ignored -- and for this project the system
    prompt is the thing holding the model to "never invent affinities", so
    losing it quietly is the worst available failure;
  - `max_tokens` is required rather than optional, and `max_tokens: 0` is a
    documented no-op that warms the prompt cache and returns no text;
  - the answer arrives as a list of content blocks, not a single string.

So the Anthropic client translates, and the translation is tested rather than
assumed. Contracts verified against the published API docs on 2026-10-19.

WHAT THIS LAYER IS FOR. Narration only. Per M6 in ROADMAP.md the model never
writes a score or a citation, so swapping providers cannot change a number this
project reports -- it changes who phrases the summary. Every client therefore
fails closed: an unusable credential raises rather than returning prose, because
an error rendered as analysis is indistinguishable from analysis.

No vendor SDKs. Both APIs are a single POST, `requests` is already a dependency,
and the offline tests monkeypatch one seam instead of three.
"""
import os
from typing import Protocol, runtime_checkable

import requests


@runtime_checkable
class ChatClient(Protocol):
    """What callers may rely on. All three clients satisfy it structurally.

    `chat` either returns non-empty text or raises LLMError; it never returns a
    provider's refusal or error notice as if it were an answer.
    """

    model: str

    def configured(self) -> bool: ...
    def health(self) -> tuple[bool, str]: ...
    def chat(self, messages: list[dict], max_tokens: int = 900) -> str: ...

# Both providers are documented to reject these rather than ignore them, so the
# defaults are chosen to be valid at the time of writing and re-checked by
# health(), which is the only thing that can tell you a model id has aged out.
OPENAI_BASE_URL = "https://api.openai.com/v1"
ANTHROPIC_BASE_URL = "https://api.anthropic.com/v1"
ANTHROPIC_VERSION = "2023-06-01"
DEFAULT_OPENAI_MODEL = "gpt-4o"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5-5"
DEFAULT_TIMEOUT = 25

PROVIDERS = ("argo", "openai", "anthropic")

TRUNCATION_NOTE = "\n\n[truncated: the response hit max_tokens before finishing]"


class LLMError(RuntimeError):
    """Base for every provider failure.

    `ArgoError` subclasses this, so callers written against Argo keep working
    and a provider-agnostic caller can catch one type.
    """


def default_timeout() -> int:
    """Request timeout in seconds, overridable with LANTERN_TIMEOUT."""
    raw = os.getenv("LANTERN_TIMEOUT", "")
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_TIMEOUT
    return value if value > 0 else DEFAULT_TIMEOUT


def split_system(messages: list[dict]) -> tuple[str, list[dict]]:
    """Hoist system turns out of an OpenAI-shaped message list.

    Returns the concatenated system text and the remaining turns. Anthropic has
    no system role; several system turns are joined with a blank line, which is
    what the OpenAI side would have concatenated into the context anyway.
    """
    system, rest = [], []
    for message in messages:
        if message.get("role") == "system":
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                system.append(content)
        else:
            rest.append(message)
    return "\n\n".join(system), rest


def openai_sampling(model: str, max_tokens: int) -> dict:
    """Per-family sampling parameters for api.openai.com.

    Deliberately NOT shared with `argo.sampling_params`, which looks almost
    identical. That one caps Anthropic models at 21000 tokens because the Argo
    gateway rejects more when not streaming -- a property of the proxy, not of
    any vendor API. Sharing the function would quietly apply a gateway's limit
    to a direct connection that does not have it.
    """
    low = (model or "").strip().lower()
    # Reasoning models renamed the field and accept only the default
    # temperature; sending the old shape is an error, not a no-op.
    if low.startswith(("o1", "o3", "o4", "gpt-5")):
        return {"max_completion_tokens": max_tokens}
    return {"temperature": 0.2, "max_tokens": max_tokens}


def _require_positive(max_tokens: int) -> int:
    """Anthropic documents max_tokens 0 as 'warm the cache, return nothing'."""
    if not isinstance(max_tokens, int) or max_tokens < 1:
        raise LLMError("max_tokens must be a positive integer.")
    return max_tokens


class OpenAIClient:
    """Chat Completions. Same wire format as Argo, different auth and failures."""

    name = "openai"
    label = "OpenAI"
    key_variable = "OPENAI_API_KEY"

    def __init__(self, base_url=None, api_key=None, model=None, timeout=None):
        self.base_url = (base_url or os.getenv("OPENAI_BASE_URL") or OPENAI_BASE_URL).rstrip("/")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or os.getenv("OPENAI_MODEL") or DEFAULT_OPENAI_MODEL
        self.timeout = timeout or default_timeout()

    def configured(self) -> bool:
        """A key and a model are present. Says nothing about whether they work."""
        return bool(self.api_key and self.model)

    def ready(self):
        return self.configured()

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"}

    def health(self) -> tuple[bool, str]:
        if not self.configured():
            return False, f"{self.key_variable} is not set in .env."
        try:
            r = requests.get(f"{self.base_url}/models", headers=self._headers(),
                             timeout=self.timeout)
        except requests.RequestException as exc:
            return False, f"OpenAI unreachable ({type(exc).__name__})."
        if r.status_code == 401:
            return False, f"OpenAI rejected {self.key_variable} (401)."
        if r.status_code == 429:
            return False, "OpenAI rate limit or quota exhausted (429)."
        try:
            r.raise_for_status()
            ids = [m.get("id") for m in r.json().get("data", [])]
        except (requests.RequestException, ValueError) as exc:
            return False, f"OpenAI model list unreadable ({type(exc).__name__})."
        if not ids:
            return False, "OpenAI returned an empty model list."
        if self.model not in ids:
            return False, (f"OPENAI_MODEL={self.model!r} is not among the {len(ids)} "
                           "models this key can reach.")
        return True, f"OpenAI reachable and {self.model} is available."

    def chat(self, messages: list[dict], max_tokens=900) -> str:
        if not self.configured():
            raise LLMError(f"Set {self.key_variable} and OPENAI_MODEL in .env for live AI analysis.")
        _require_positive(max_tokens)
        payload = {"model": self.model, "messages": messages}
        payload.update(openai_sampling(self.model, max_tokens))
        try:
            r = requests.post(f"{self.base_url}/chat/completions", json=payload,
                              headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            raise LLMError(f"OpenAI request failed: {type(exc).__name__}.") from exc
        _raise_for_api_error(r, "OpenAI", self.key_variable)
        try:
            body = r.json()
            choice = body["choices"][0]
            message = choice["message"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise LLMError("OpenAI returned a response with no message content.") from exc
        # Checking the key exists is not enough: a wrongly-typed value makes the
        # accessors below raise AttributeError, which is not an LLMError and so
        # escapes the one handler app.py installs.
        if not isinstance(choice, dict) or not isinstance(message, dict):
            raise LLMError("OpenAI returned a malformed message object.")

        # A refusal arrives as content=None with the reason in a sibling field.
        # Without this branch it reads as "empty response", which hides a
        # refusal the user needs to see.
        refusal = message.get("refusal")
        if refusal:
            raise LLMError(f"OpenAI refused the request: {refusal}")

        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise LLMError("OpenAI returned an empty or non-text response.")
        if choice.get("finish_reason") == "length":
            content += TRUNCATION_NOTE
        return content


class AnthropicClient:
    """Messages API. Translates the OpenAI-shaped call this project makes."""

    name = "anthropic"
    label = "Anthropic (Claude)"
    key_variable = "ANTHROPIC_API_KEY"

    def __init__(self, base_url=None, api_key=None, model=None, timeout=None):
        self.base_url = (base_url or os.getenv("ANTHROPIC_BASE_URL") or ANTHROPIC_BASE_URL).rstrip("/")
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model or os.getenv("ANTHROPIC_MODEL") or DEFAULT_ANTHROPIC_MODEL
        self.timeout = timeout or default_timeout()

    def configured(self) -> bool:
        return bool(self.api_key and self.model)

    def ready(self):
        return self.configured()

    def _headers(self) -> dict:
        return {"x-api-key": self.api_key,
                "anthropic-version": ANTHROPIC_VERSION,
                "content-type": "application/json"}

    def health(self) -> tuple[bool, str]:
        if not self.configured():
            return False, f"{self.key_variable} is not set in .env."
        try:
            r = requests.get(f"{self.base_url}/models", headers=self._headers(),
                             timeout=self.timeout)
        except requests.RequestException as exc:
            return False, f"Anthropic unreachable ({type(exc).__name__})."
        if r.status_code == 401:
            return False, f"Anthropic rejected {self.key_variable} (401)."
        if r.status_code == 429:
            return False, "Anthropic rate limit reached (429)."
        # Listing models is a convenience, not part of the Messages contract.
        # If it is absent the credential may still be fine, so this reports
        # "unverified" rather than failing closed on a secondary endpoint.
        if r.status_code == 404:
            return True, (f"Anthropic reachable; model list unavailable, so "
                          f"{self.model} is unverified until the first query.")
        try:
            r.raise_for_status()
            ids = [m.get("id") for m in r.json().get("data", [])]
        except (requests.RequestException, ValueError) as exc:
            return False, f"Anthropic model list unreadable ({type(exc).__name__})."
        if not ids:
            return True, f"Anthropic reachable; {self.model} unverified (empty model list)."
        if self.model not in ids:
            return False, (f"ANTHROPIC_MODEL={self.model!r} is not among the {len(ids)} "
                           "models this key can reach.")
        return True, f"Anthropic reachable and {self.model} is available."

    def chat(self, messages: list[dict], max_tokens=900) -> str:
        if not self.configured():
            raise LLMError(f"Set {self.key_variable} in .env for live AI analysis.")
        _require_positive(max_tokens)
        system, turns = split_system(messages)
        if not turns:
            raise LLMError("Anthropic needs at least one user turn besides the system prompt.")
        payload = {"model": self.model, "max_tokens": max_tokens, "messages": turns}
        if system:
            payload["system"] = system
        try:
            r = requests.post(f"{self.base_url}/messages", json=payload,
                              headers=self._headers(), timeout=self.timeout)
        except requests.RequestException as exc:
            raise LLMError(f"Anthropic request failed: {type(exc).__name__}.") from exc
        _raise_for_api_error(r, "Anthropic", self.key_variable)
        try:
            body = r.json()
            blocks = body["content"]
        except (ValueError, KeyError, TypeError) as exc:
            raise LLMError("Anthropic returned a response with no content blocks.") from exc
        # Same reason as the OpenAI branch: `"content": null` would otherwise
        # leave the loop below raising TypeError past the LLMError contract.
        if not isinstance(blocks, list):
            raise LLMError("Anthropic returned a malformed content field.")

        # content is a list of typed blocks. Anything that is not text -- a
        # tool_use or a thinking block -- is skipped rather than stringified.
        text = "".join(b.get("text", "") for b in blocks
                       if isinstance(b, dict) and b.get("type") == "text")
        if not text.strip():
            raise LLMError("Anthropic returned no text content.")
        if body.get("stop_reason") == "max_tokens":
            text += TRUNCATION_NOTE
        return text


def _raise_for_api_error(response, provider: str, key_variable: str) -> None:
    """Turn an HTTP error into an LLMError that names the cause, not the key.

    Both providers return a JSON envelope with a human-readable message; it is
    quoted because "401" alone does not tell a user whether the key is wrong,
    expired, or out of credit. The key value itself is never interpolated.
    """
    if response.status_code < 400:
        return
    detail = ""
    try:
        body = response.json()
        error = body.get("error") if isinstance(body, dict) else None
        if isinstance(error, dict):
            detail = str(error.get("message") or error.get("type") or "")
    except ValueError:
        detail = ""
    hint = {
        401: f"{key_variable} was rejected.",
        402: "Billing problem on the account.",
        403: "This key lacks permission for that model.",
        404: "Endpoint or model not found -- check the model id.",
        429: "Rate limit or quota exhausted.",
        500: "Provider-side error.",
        529: "Provider temporarily overloaded.",
    }.get(response.status_code, "")
    parts = [f"{provider} returned HTTP {response.status_code}."]
    if hint:
        parts.append(hint)
    if detail:
        parts.append(detail[:300])
    raise LLMError(" ".join(parts))


def make_client(provider: str | None = None, **kwargs):
    """Build the client named by `provider`, or by LLM_PROVIDER, default argo.

    ArgoClient is imported here rather than at module scope because `argo`
    imports LLMError from this module; a top-level import would be circular.
    """
    name = (provider or os.getenv("LLM_PROVIDER") or "argo").strip().lower()
    if name == "argo":
        from .argo import ArgoClient
        return ArgoClient(**kwargs)
    if name == "openai":
        return OpenAIClient(**kwargs)
    if name == "anthropic":
        return AnthropicClient(**kwargs)
    raise LLMError(f"Unknown LLM_PROVIDER {name!r}. Choose one of: {', '.join(PROVIDERS)}.")


def provider_status() -> list[dict]:
    """One row per provider for the UI: name, label, and whether it is set up.

    Never returns a credential, only whether one is present.
    """
    rows = []
    for name in PROVIDERS:
        try:
            client = make_client(name)
            rows.append({"name": name, "label": getattr(client, "label", name.title()),
                         "model": client.model, "configured": client.configured()})
        except LLMError:
            continue
    return rows
