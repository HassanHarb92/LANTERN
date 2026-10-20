"""Offline tests for the OpenAI and Anthropic clients. No network access.

Every request is intercepted at `requests.post`/`requests.get`, so these also
assert on what we *send*, which is where the Anthropic translation can go wrong
without any error being raised.
"""
import json
import pytest
import requests

from lantern import llm
from lantern.agent import SYSTEM, explain_campaign
from lantern.argo import ArgoError
from lantern.llm import (AnthropicClient, LLMError, OpenAIClient, default_timeout,
                         make_client, openai_sampling, provider_status, split_system)

PROVIDER_VARS = ("LLM_PROVIDER", "LANTERN_TIMEOUT",
                 "OPENAI_API_KEY", "OPENAI_MODEL", "OPENAI_BASE_URL",
                 "ANTHROPIC_API_KEY", "ANTHROPIC_MODEL", "ANTHROPIC_BASE_URL",
                 "ARGO_USER", "ARGO_API_KEY", "ARGO_MODEL")


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """A developer's real .env must not decide whether these tests pass."""
    for var in PROVIDER_VARS:
        monkeypatch.delenv(var, raising=False)


class FakeResponse:
    def __init__(self, payload, status_code=200, text_body=None):
        self._payload = payload
        self.status_code = status_code
        self.text = text_body or ""

    def json(self):
        if self._payload is _INVALID_JSON:
            raise ValueError("not json")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}")


_INVALID_JSON = object()


def capture_post(monkeypatch, response):
    """Swap in a fake POST and return a dict that fills with what was sent."""
    sent = {}

    def fake_post(url, json=None, headers=None, timeout=None):
        sent.update(url=url, payload=json, headers=headers, timeout=timeout)
        return response

    monkeypatch.setattr(llm.requests, "post", fake_post)
    return sent


def anthropic_body(text="An answer.", stop_reason="end_turn"):
    return {"id": "msg_1", "type": "message", "role": "assistant",
            "content": [{"type": "text", "text": text}], "stop_reason": stop_reason}


def openai_body(content="An answer.", finish_reason="stop", refusal=None):
    message = {"role": "assistant", "content": content}
    if refusal is not None:
        message["refusal"] = refusal
    return {"id": "chatcmpl-1", "choices": [{"index": 0, "message": message,
                                             "finish_reason": finish_reason}]}


class TestSystemPromptSurvivesTranslation:
    """The system turn is what forbids inventing affinities. Anthropic has no
    system role, so a client that forwards the message list unchanged loses the
    one instruction this project cannot afford to lose -- silently, with a
    perfectly normal-looking answer coming back."""

    def test_system_message_is_hoisted_to_top_level(self, monkeypatch):
        sent = capture_post(monkeypatch, FakeResponse(anthropic_body()))
        client = AnthropicClient(api_key="k", model="claude-sonnet-5-5")
        client.chat([{"role": "system", "content": "BE CAREFUL"},
                     {"role": "user", "content": "hi"}])
        assert sent["payload"]["system"] == "BE CAREFUL"

    def test_no_system_role_is_left_in_the_message_list(self, monkeypatch):
        sent = capture_post(monkeypatch, FakeResponse(anthropic_body()))
        AnthropicClient(api_key="k").chat([{"role": "system", "content": "S"},
                                           {"role": "user", "content": "hi"}])
        roles = [m["role"] for m in sent["payload"]["messages"]]
        assert "system" not in roles and roles == ["user"]

    def test_real_agent_system_prompt_is_transmitted_whole(self, monkeypatch):
        """Guards the actual wiring, not a stand-in string."""
        sent = capture_post(monkeypatch, FakeResponse(anthropic_body()))
        campaign = {"target": "Nd3+", "competitor": "Ca2+", "mode": "curated reference set",
                    "disclaimer": "heuristic only", "candidates": []}
        explain_campaign(campaign, AnthropicClient(api_key="k"), "why?")
        assert sent["payload"]["system"] == SYSTEM
        assert "never invent" in sent["payload"]["system"].lower()

    def test_several_system_turns_are_joined_not_dropped(self):
        system, rest = split_system([{"role": "system", "content": "one"},
                                     {"role": "system", "content": "two"},
                                     {"role": "user", "content": "q"}])
        assert system == "one\n\ntwo" and len(rest) == 1

    def test_system_only_conversation_is_refused(self, monkeypatch):
        monkeypatch.setattr(llm.requests, "post", _explode)
        with pytest.raises(LLMError, match="at least one user turn"):
            AnthropicClient(api_key="k").chat([{"role": "system", "content": "S"}])

    def test_blank_system_turn_is_not_sent_as_empty_string(self, monkeypatch):
        sent = capture_post(monkeypatch, FakeResponse(anthropic_body()))
        AnthropicClient(api_key="k").chat([{"role": "system", "content": "   "},
                                           {"role": "user", "content": "hi"}])
        assert "system" not in sent["payload"]


def _explode(*args, **kwargs):
    raise AssertionError("no request should have been made")


class TestAnthropicRequestShape:
    def test_required_headers(self, monkeypatch):
        sent = capture_post(monkeypatch, FakeResponse(anthropic_body()))
        AnthropicClient(api_key="secret-key").chat([{"role": "user", "content": "hi"}])
        assert sent["headers"]["anthropic-version"] == "2023-06-01"
        assert sent["headers"]["x-api-key"] == "secret-key"
        assert "Authorization" not in sent["headers"]

    def test_max_tokens_is_always_present(self, monkeypatch):
        sent = capture_post(monkeypatch, FakeResponse(anthropic_body()))
        AnthropicClient(api_key="k").chat([{"role": "user", "content": "hi"}], max_tokens=512)
        assert sent["payload"]["max_tokens"] == 512

    def test_zero_max_tokens_refused_before_sending(self, monkeypatch):
        # Documented as "populate the cache, generate nothing" -- a request
        # that costs money and returns no narration.
        monkeypatch.setattr(llm.requests, "post", _explode)
        with pytest.raises(LLMError, match="positive integer"):
            AnthropicClient(api_key="k").chat([{"role": "user", "content": "hi"}], max_tokens=0)

    def test_endpoint_is_messages_not_chat_completions(self, monkeypatch):
        sent = capture_post(monkeypatch, FakeResponse(anthropic_body()))
        AnthropicClient(api_key="k").chat([{"role": "user", "content": "hi"}])
        assert sent["url"].endswith("/messages")


class TestAnthropicResponseParsing:
    def test_concatenates_every_text_block(self, monkeypatch):
        body = {"content": [{"type": "text", "text": "part one. "},
                            {"type": "text", "text": "part two."}]}
        capture_post(monkeypatch, FakeResponse(body))
        out = AnthropicClient(api_key="k").chat([{"role": "user", "content": "hi"}])
        assert out == "part one. part two."

    def test_non_text_blocks_are_skipped_not_stringified(self, monkeypatch):
        body = {"content": [{"type": "thinking", "thinking": "hmm"},
                            {"type": "text", "text": "the answer"}]}
        capture_post(monkeypatch, FakeResponse(body))
        assert AnthropicClient(api_key="k").chat([{"role": "user", "content": "x"}]) == "the answer"

    def test_no_text_blocks_raises_rather_than_returning_empty(self, monkeypatch):
        capture_post(monkeypatch, FakeResponse({"content": [{"type": "tool_use", "id": "t"}]}))
        with pytest.raises(LLMError, match="no text content"):
            AnthropicClient(api_key="k").chat([{"role": "user", "content": "x"}])

    def test_truncation_is_disclosed(self, monkeypatch):
        capture_post(monkeypatch, FakeResponse(anthropic_body("half a caveat", "max_tokens")))
        out = AnthropicClient(api_key="k").chat([{"role": "user", "content": "x"}])
        assert "truncated" in out and out.startswith("half a caveat")

    def test_missing_content_key_raises(self, monkeypatch):
        capture_post(monkeypatch, FakeResponse({"id": "msg_1"}))
        with pytest.raises(LLMError, match="no content blocks"):
            AnthropicClient(api_key="k").chat([{"role": "user", "content": "x"}])


class TestMalformedBodiesStayInsideTheContract:
    """A body can be valid JSON and still have the wrong *types*. Those paths
    must raise LLMError like any other failure: app.py installs exactly one
    handler, `except LLMError`, so a stray TypeError reaches the user as a
    Streamlit traceback rather than a readable message."""

    @pytest.mark.parametrize("body", [
        {"choices": [{"message": "oops"}]},          # message is a string
        {"choices": [{"message": None}]},            # message is null
        {"choices": ["not-a-dict"]},                 # choice is not a mapping
    ])
    def test_openai_malformed_message_raises_llm_error(self, monkeypatch, body):
        capture_post(monkeypatch, FakeResponse(body))
        with pytest.raises(LLMError):
            OpenAIClient(api_key="k", model="gpt-4o").chat([{"role": "user", "content": "x"}])

    @pytest.mark.parametrize("body", [
        {"content": None},                           # null content
        {"content": {"type": "text", "text": "hi"}}, # a single block, not a list
        {"content": 42},
    ])
    def test_anthropic_malformed_content_raises_llm_error(self, monkeypatch, body):
        capture_post(monkeypatch, FakeResponse(body))
        with pytest.raises(LLMError):
            AnthropicClient(api_key="k").chat([{"role": "user", "content": "x"}])

    def test_blocks_that_are_not_dicts_are_skipped(self, monkeypatch):
        capture_post(monkeypatch, FakeResponse({"content": ["raw", {"type": "text", "text": "ok"}]}))
        assert AnthropicClient(api_key="k").chat([{"role": "user", "content": "x"}]) == "ok"


class TestOpenAIClient:
    def test_bearer_auth_and_endpoint(self, monkeypatch):
        sent = capture_post(monkeypatch, FakeResponse(openai_body()))
        OpenAIClient(api_key="sk-test", model="gpt-4o").chat([{"role": "user", "content": "hi"}])
        assert sent["headers"]["Authorization"] == "Bearer sk-test"
        assert sent["url"].endswith("/chat/completions")

    def test_system_role_is_passed_through_unchanged(self, monkeypatch):
        """The mirror image of the Anthropic test: here the role is native and
        hoisting it would be the bug."""
        sent = capture_post(monkeypatch, FakeResponse(openai_body()))
        OpenAIClient(api_key="k", model="gpt-4o").chat(
            [{"role": "system", "content": "S"}, {"role": "user", "content": "hi"}])
        assert [m["role"] for m in sent["payload"]["messages"]] == ["system", "user"]
        assert "system" not in sent["payload"]

    def test_refusal_is_reported_as_a_refusal(self, monkeypatch):
        # content is null on a refusal; without the dedicated branch this
        # surfaces as "empty response" and hides why.
        capture_post(monkeypatch, FakeResponse(openai_body(content=None, refusal="I can't help.")))
        with pytest.raises(LLMError, match="refused the request: I can't help."):
            OpenAIClient(api_key="k", model="gpt-4o").chat([{"role": "user", "content": "x"}])

    def test_empty_content_raises(self, monkeypatch):
        capture_post(monkeypatch, FakeResponse(openai_body(content="   ")))
        with pytest.raises(LLMError, match="empty or non-text"):
            OpenAIClient(api_key="k", model="gpt-4o").chat([{"role": "user", "content": "x"}])

    def test_length_finish_reason_is_disclosed(self, monkeypatch):
        capture_post(monkeypatch, FakeResponse(openai_body("cut off", finish_reason="length")))
        out = OpenAIClient(api_key="k", model="gpt-4o").chat([{"role": "user", "content": "x"}])
        assert "truncated" in out

    def test_unconfigured_raises_before_any_request(self, monkeypatch):
        monkeypatch.setattr(llm.requests, "post", _explode)
        client = OpenAIClient(api_key="", model="gpt-4o")
        with pytest.raises(LLMError, match="OPENAI_API_KEY"):
            client.chat([{"role": "user", "content": "x"}])


class TestOpenAISampling:
    """api.openai.com rejects the wrong parameter shape rather than ignoring it."""

    def test_reasoning_models_use_completion_tokens_and_no_temperature(self):
        assert openai_sampling("o3-mini", 900) == {"max_completion_tokens": 900}
        assert openai_sampling("gpt-5.1", 900) == {"max_completion_tokens": 900}

    def test_standard_models_keep_deterministic_temperature(self):
        assert openai_sampling("gpt-4o", 900) == {"temperature": 0.2, "max_tokens": 900}

    def test_does_not_inherit_the_argo_anthropic_cap(self):
        """argo.sampling_params caps Anthropic models at 21000 because the
        gateway rejects more. That is the proxy's limit, not OpenAI's, and it
        must not leak into a direct connection."""
        assert openai_sampling("gpt-4o", 99_000)["max_tokens"] == 99_000


class TestCredentialsNeverLeak:
    """`.env` discipline is only as good as the error messages. A key echoed
    into a Streamlit error lands in screenshots, logs and bug reports."""

    SECRET = "sk-DO-NOT-ECHO-abcdef123456"

    @pytest.mark.parametrize("status", [401, 403, 429, 500, 529])
    def test_http_error_text_excludes_the_key(self, monkeypatch, status):
        body = {"type": "error", "error": {"type": "authentication_error",
                                           "message": "invalid x-api-key"}}
        capture_post(monkeypatch, FakeResponse(body, status_code=status))
        for client in (OpenAIClient(api_key=self.SECRET, model="gpt-4o"),
                       AnthropicClient(api_key=self.SECRET)):
            with pytest.raises(LLMError) as caught:
                client.chat([{"role": "user", "content": "x"}])
            assert self.SECRET not in str(caught.value)
            assert str(status) in str(caught.value)

    def test_transport_failure_text_excludes_the_key(self, monkeypatch):
        def boom(*args, **kwargs):
            raise requests.ConnectionError(f"failed to connect with key {self.SECRET}")

        monkeypatch.setattr(llm.requests, "post", boom)
        with pytest.raises(LLMError) as caught:
            OpenAIClient(api_key=self.SECRET, model="gpt-4o").chat([{"role": "user", "content": "x"}])
        # The underlying exception carries the key; only its type is reported.
        assert self.SECRET not in str(caught.value)
        assert "ConnectionError" in str(caught.value)

    def test_health_text_excludes_the_key(self, monkeypatch):
        monkeypatch.setattr(llm.requests, "get",
                            lambda *a, **k: FakeResponse({"error": {"message": "bad key"}}, 401))
        for client in (OpenAIClient(api_key=self.SECRET, model="gpt-4o"),
                       AnthropicClient(api_key=self.SECRET)):
            ok, detail = client.health()
            assert not ok and self.SECRET not in detail

    def test_error_body_is_quoted_but_bounded(self, monkeypatch):
        """Provider text is echoed to explain the failure; it is cut so a long
        or hostile body cannot flood the UI."""
        capture_post(monkeypatch, FakeResponse(
            {"error": {"message": "x" * 5000}}, status_code=400))
        with pytest.raises(LLMError) as caught:
            OpenAIClient(api_key="k", model="gpt-4o").chat([{"role": "user", "content": "x"}])
        assert len(str(caught.value)) < 500

    def test_non_json_error_body_still_raises_cleanly(self, monkeypatch):
        capture_post(monkeypatch, FakeResponse(_INVALID_JSON, status_code=502))
        with pytest.raises(LLMError, match="502"):
            OpenAIClient(api_key="k", model="gpt-4o").chat([{"role": "user", "content": "x"}])


class TestHealth:
    def test_openai_rejects_a_model_the_key_cannot_reach(self, monkeypatch):
        monkeypatch.setattr(llm.requests, "get",
                            lambda *a, **k: FakeResponse({"data": [{"id": "gpt-4o"}]}))
        ok, detail = OpenAIClient(api_key="k", model="gpt-9-imaginary").health()
        assert not ok and "gpt-9-imaginary" in detail

    def test_openai_accepts_a_listed_model(self, monkeypatch):
        monkeypatch.setattr(llm.requests, "get",
                            lambda *a, **k: FakeResponse({"data": [{"id": "gpt-4o"}]}))
        ok, _ = OpenAIClient(api_key="k", model="gpt-4o").health()
        assert ok

    def test_anthropic_missing_model_list_does_not_fail_closed(self, monkeypatch):
        """Listing models is a convenience, not part of the Messages contract.
        A 404 there says nothing about whether the credential works."""
        monkeypatch.setattr(llm.requests, "get", lambda *a, **k: FakeResponse({}, 404))
        ok, detail = AnthropicClient(api_key="k").health()
        assert ok and "unverified" in detail

    def test_unreachable_provider_is_reported_not_raised(self, monkeypatch):
        def boom(*args, **kwargs):
            raise requests.ConnectionError("down")

        monkeypatch.setattr(llm.requests, "get", boom)
        ok, detail = OpenAIClient(api_key="k", model="gpt-4o").health()
        assert not ok and "unreachable" in detail

    def test_unconfigured_health_makes_no_request(self, monkeypatch):
        monkeypatch.setattr(llm.requests, "get", _explode)
        ok, detail = AnthropicClient(api_key="").health()
        assert not ok and "ANTHROPIC_API_KEY" in detail


class TestFactory:
    def test_defaults_to_argo_when_unset(self):
        assert make_client().name == "argo"

    def test_env_var_selects_provider(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        assert isinstance(make_client(), AnthropicClient)

    def test_explicit_argument_overrides_env(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "anthropic")
        assert isinstance(make_client("openai"), OpenAIClient)

    def test_case_and_whitespace_tolerated(self, monkeypatch):
        monkeypatch.setenv("LLM_PROVIDER", "  OpenAI \n")
        assert isinstance(make_client(), OpenAIClient)

    def test_unknown_provider_names_the_valid_choices(self):
        with pytest.raises(LLMError, match="argo, openai, anthropic"):
            make_client("gemini")

    def test_argo_error_is_catchable_as_llm_error(self):
        """app.py catches LLMError once for all three providers."""
        assert issubclass(ArgoError, LLMError)

    def test_every_provider_satisfies_the_client_protocol(self):
        for name in llm.PROVIDERS:
            client = make_client(name)
            for method in ("configured", "health", "chat"):
                assert callable(getattr(client, method)), f"{name} lacks {method}"
            assert isinstance(client.label, str) and client.label

    def test_provider_status_reports_configuration_without_credentials(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-secret-value")
        rows = provider_status()
        assert {r["name"] for r in rows} == set(llm.PROVIDERS)
        assert next(r for r in rows if r["name"] == "openai")["configured"] is True
        assert next(r for r in rows if r["name"] == "anthropic")["configured"] is False
        assert "sk-secret-value" not in json.dumps(rows)


class TestTimeout:
    def test_default_when_unset(self):
        assert default_timeout() == 25

    def test_env_override(self, monkeypatch):
        monkeypatch.setenv("LANTERN_TIMEOUT", "7")
        assert default_timeout() == 7

    def test_garbage_falls_back_rather_than_crashing(self, monkeypatch):
        monkeypatch.setenv("LANTERN_TIMEOUT", "soon")
        assert default_timeout() == 25

    def test_nonpositive_falls_back(self, monkeypatch):
        # requests treats timeout=0 as "fail immediately".
        monkeypatch.setenv("LANTERN_TIMEOUT", "0")
        assert default_timeout() == 25

    def test_applied_to_every_provider(self, monkeypatch):
        monkeypatch.setenv("LANTERN_TIMEOUT", "11")
        for name in llm.PROVIDERS:
            assert make_client(name).timeout == 11
