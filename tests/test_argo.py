"""Offline tests for the Argo client's fail-closed behaviour. No network access."""
import pytest
from reefinder.argo import (ArgoClient, ArgoError, reject_if_blocked, sampling_params,
                            ANTHROPIC_MAX_TOKENS)


class TestBlockedResponseDetection:
    """Argo answers a rejected credential with HTTP 200 and a complete chat
    completion whose content is an ACCESS DENIED notice. Rendering that as
    analysis is the failure these guards exist to prevent."""

    def test_blocked_id_prefix_raises(self):
        body = {"id": "chatcmpl-blocked-abc123",
                "choices": [{"message": {"content": "ACCESS DENIED"}}],
                "usage": {"total_tokens": 12}}
        with pytest.raises(ArgoError, match="rejected the credential"):
            reject_if_blocked(body)

    def test_zero_total_tokens_raises(self):
        body = {"id": "chatcmpl-ok",
                "choices": [{"message": {"content": "ACCESS DENIED"}}],
                "usage": {"total_tokens": 0}}
        with pytest.raises(ArgoError, match="zero-token"):
            reject_if_blocked(body)

    def test_genuine_response_passes(self):
        body = {"id": "chatcmpl-ok", "choices": [{"message": {"content": "A real answer."}}],
                "usage": {"total_tokens": 184}}
        reject_if_blocked(body)  # must not raise

    def test_missing_usage_block_is_not_treated_as_blocked(self):
        reject_if_blocked({"id": "chatcmpl-ok", "choices": [{"message": {"content": "hi"}}]})


class TestSamplingParams:
    """Argo's model families reject the wrong parameter shape rather than
    ignoring it, so one hard-coded set cannot serve all of them."""

    def test_o_series_uses_completion_tokens_and_no_temperature(self):
        params = sampling_params("o3-mini", 900)
        assert params == {"max_completion_tokens": 900}

    def test_gpt5_omits_temperature(self):
        # GPT-5.x accepts temperature only if it is exactly 1.
        params = sampling_params("GPT-5.6 Luna", 900)
        assert "temperature" not in params
        assert params["max_tokens"] == 900

    def test_anthropic_caps_max_tokens(self):
        params = sampling_params("Claude Opus 5", 99_000)
        assert params["max_tokens"] == ANTHROPIC_MAX_TOKENS

    def test_other_families_keep_deterministic_temperature(self):
        params = sampling_params("Gemini 3.5 Flash", 900)
        assert params["temperature"] == 0.2 and params["max_tokens"] == 900

    def test_gpt4_is_not_mistaken_for_gpt5(self):
        assert sampling_params("GPT-4o", 900)["temperature"] == 0.2


class TestConfiguration:
    def test_unconfigured_client_is_not_ready(self, monkeypatch):
        for var in ("ARGO_USER", "ARGO_API_KEY", "ARGO_MODEL"):
            monkeypatch.delenv(var, raising=False)
        assert not ArgoClient().configured()

    def test_legacy_api_key_variable_still_read(self, monkeypatch):
        monkeypatch.delenv("ARGO_USER", raising=False)
        monkeypatch.setenv("ARGO_API_KEY", "someuser")
        monkeypatch.setenv("ARGO_MODEL", "Claude Sonnet 5")
        assert ArgoClient().configured()

    def test_argo_user_takes_precedence(self, monkeypatch):
        monkeypatch.setenv("ARGO_USER", "preferred")
        monkeypatch.setenv("ARGO_API_KEY", "legacy")
        assert ArgoClient(model="m").user == "preferred"

    def test_chat_without_configuration_raises_before_any_request(self, monkeypatch):
        for var in ("ARGO_USER", "ARGO_API_KEY", "ARGO_MODEL"):
            monkeypatch.delenv(var, raising=False)
        with pytest.raises(ArgoError, match="ARGO_USER"):
            ArgoClient().chat([{"role": "user", "content": "hi"}])

    def test_health_reports_unconfigured_without_network(self, monkeypatch):
        for var in ("ARGO_USER", "ARGO_API_KEY", "ARGO_MODEL"):
            monkeypatch.delenv(var, raising=False)
        ok, detail = ArgoClient().health()
        assert not ok and "not both set" in detail
