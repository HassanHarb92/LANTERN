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

# A model can be named two ways and Argo takes either. Its /v1/models endpoint
# lists display names ("Claude Sonnet 5", "GPT-5.1", "o3-mini"); the Argo API
# documentation's model table lists compact ids ("claudesonnet5", "gpt51"). Both
# were sent to the live gateway and both answered, resolving to the same build.
# So family detection must recognise either, which is what canonical_model is
# for -- and nothing here may reject a name merely for being the other spelling.
#
# Getting this wrong is not hypothetical: an earlier version matched only vendor
# spellings, so none of the compact ids matched any branch and every one of them
# was sent the parameter shape its family rejects.

# "gpto1", "gpto3mini", "gpto4mini", and the bare "o1"/"o3mini" someone may
# write from habit. Not "gpt4o": the o there is a suffix, not the series.
_O_SERIES = re.compile(r"^(?:gpt)?o\d")

# Anthropic models on Argo reject max_tokens above this when not streaming.
# Verified live: without an explicit max_tokens the gateway defaults to a value
# large enough that its Anthropic SDK refuses the non-streaming request outright
# ("Streaming is required for operations that may take longer than 10 minutes"),
# so sending this cap is what makes the whole claude family usable here.
ANTHROPIC_MAX_TOKENS = 21000

# Claude models that answer 400 "`temperature` is deprecated for this model".
# Verified live on 2026-10-20: claudesonnet5 rejects it, while claudeopus5,
# claudesonnet46 and claudehaiku45 all accept it -- so this is per-model, not
# per-generation, and cannot be inferred from the name. Seeded with what is
# known and extended at runtime by chat(), which retries once when a model
# turns out to belong here. Canonical spellings only.
TEMPERATURE_REJECTED = {"claudesonnet5"}

# The gateway's wording for that refusal, matched loosely because the prose is
# the vendor's and free to change; the retry is harmless if it never matches.
_TEMPERATURE_REFUSED = re.compile(r"temperature.{0,40}(deprecated|not supported|unsupported)",
                                  re.IGNORECASE | re.DOTALL)

# Used when ARGO_USER is set but ARGO_MODEL is not, so the gateway is usable
# with one setting the way openai and anthropic already are. Terra is the
# cost-balanced tier of the current GPT-5.6 family, which is ample for the only
# job the model has here -- narrating results it is handed. Argo's catalogue
# moves monthly; health() checks this id against /models rather than trusting
# it, and ARGO_MODEL overrides it.
DEFAULT_ARGO_MODEL = "gpt56terra"


def canonical_model(model: str) -> str:
    """An Argo id reduced to its comparable form: lowercase, separators gone.

    A valid id is already its own canonical form, so this only ever changes a
    name a human typed in vendor style -- "GPT-5.1" and "Claude Sonnet 5"
    collapse onto "gpt51" and "claudesonnet5", which are the real ids. Used for
    family detection, never for the string actually sent: rewriting a user's
    model id would hide the typo rather than report it.
    """
    return re.sub(r"[^a-z0-9]", "", (model or "").lower())


def sampling_params(model: str, max_tokens: int) -> dict:
    """Per-family sampling parameters, per the Argo model table.

    Argo's families disagree about these, and sending the wrong shape is an
    error rather than a silently ignored field:
      - o-series take max_completion_tokens and neither temperature nor top_p;
      - GPT-5.x and GPT-4.1 take max_completion_tokens and reject max_tokens;
      - GPT-5.x additionally pins temperature (gpt55 accepts only exactly 1, and
        the gpt56 entries do not restate their parameter list), so omitting it
        is the only choice valid for every member of the family;
      - Anthropic models require an explicit max_tokens, capped when not
        streaming, and accept at most one of temperature/top_p -- so never both,
        and none at all for those in TEMPERATURE_REJECTED;
      - everything else, including gpt4o and the Gemini models, takes the
        ordinary temperature plus max_tokens pair.

    Temperature is 0.2 wherever it is allowed. This layer only narrates results
    it is handed, so the determinism is worth more than the variety.
    """
    name = canonical_model(model)
    if _O_SERIES.match(name):
        return {"max_completion_tokens": max_tokens}
    if name.startswith("gpt5"):
        return {"max_completion_tokens": max_tokens}
    if name.startswith("gpt41"):
        return {"temperature": 0.2, "max_completion_tokens": max_tokens}
    if name.startswith("claude"):
        params = {"max_tokens": min(max_tokens, ANTHROPIC_MAX_TOKENS)}
        if name not in TEMPERATURE_REJECTED:
            params["temperature"] = 0.2
        return params
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
        self.model = model or os.getenv("ARGO_MODEL") or DEFAULT_ARGO_MODEL
        self.timeout = timeout or default_timeout()

    def configured(self) -> bool:
        """The username is present; the model always is, defaulted if unset.
        Says nothing about whether either works -- that is health()'s job."""
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
            return False, "ARGO_USER is not set in .env (your ANL domain username)."
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
        # Compared canonically because /models answers in display names while
        # the API docs list compact ids, and the gateway accepts both. A literal
        # comparison would call a perfectly good ARGO_MODEL unavailable for
        # being spelled the other way.
        offered = {canonical_model(i): i for i in ids if i}
        listed = offered.get(canonical_model(self.model))
        if listed is None:
            return False, f"ARGO_MODEL={self.model!r} is not among the {len(ids)} models Argo offers."
        shown = "" if listed == self.model else f" (listed as {listed!r})"
        return True, (f"Gateway reachable and {self.model} is available{shown} "
                      f"(credential unverified until first query).")

    def _post(self, payload: dict):
        """One POST to the chat endpoint, or None if it never reached the gateway.

        Returns the response rather than raising on status, so chat() can read a
        400 body before deciding whether it is recoverable.
        """
        try:
            return requests.post(f"{self.base_url}/chat/completions", json=payload,
                                 headers={"Authorization": f"Bearer {self.user}",
                                          "Content-Type": "application/json"},
                                 timeout=self.timeout)
        except requests.RequestException:
            return None

    def chat(self, messages: list[dict], max_tokens=900) -> str:
        if not self.configured():
            raise ArgoError("Set ARGO_USER (your ANL domain username) in .env for live AI analysis. "
                            f"ARGO_MODEL is optional and defaults to {DEFAULT_ARGO_MODEL}.")
        payload = {"model": self.model, "messages": messages, "user": self.user}
        payload.update(sampling_params(self.model, max_tokens))
        r = self._post(payload)

        # A model may refuse temperature even though its family accepts it, and
        # the catalogue moves faster than any list kept here. The gateway says
        # so in plain words, so take it at its word once, remember it for the
        # rest of the process, and retry without. Any other 400 is a real error.
        if r is not None and r.status_code == 400 and "temperature" in payload:
            if _TEMPERATURE_REFUSED.search(r.text or ""):
                TEMPERATURE_REJECTED.add(canonical_model(self.model))
                payload.pop("temperature")
                r = self._post(payload)

        try:
            if r is None:
                raise requests.RequestException("no response")
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
