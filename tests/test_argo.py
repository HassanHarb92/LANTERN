"""Offline tests for the Argo client's fail-closed behaviour. No network access."""
import pytest
from lantern import argo
from lantern.argo import (ArgoClient, ArgoError, canonical_model, reject_if_blocked,
                            sampling_params, ANTHROPIC_MAX_TOKENS, TEMPERATURE_REJECTED)
from lantern.llm import LLMError


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
    ignoring it, so one hard-coded set cannot serve all of them.

    Every case here names a model the way Argo's table does -- "gpt51", not
    "GPT-5.1". That distinction is the whole point: an earlier version matched
    vendor spellings, so no real id matched any branch and every model was sent
    the fallback shape. The tests passed because they asked the same wrong
    question as the code. Display names are covered separately, below.
    """

    def test_o_series_uses_completion_tokens_and_no_temperature(self):
        for model in ("gpto1", "gpto3", "gpto3mini", "gpto4mini"):
            assert sampling_params(model, 900) == {"max_completion_tokens": 900}, model

    def test_gpt5_family_rejects_max_tokens_and_pins_temperature(self):
        # The table says GPT-5.x does not accept max_tokens; gpt55 accepts
        # temperature only when it is exactly 1, so it is omitted for all.
        for model in ("gpt5", "gpt5mini", "gpt51", "gpt52", "gpt54", "gpt55",
                      "gpt56sol", "gpt56terra", "gpt56luna"):
            assert sampling_params(model, 900) == {"max_completion_tokens": 900}, model

    def test_gpt41_family_takes_temperature_with_completion_tokens(self):
        for model in ("gpt41", "gpt41mini", "gpt41nano"):
            params = sampling_params(model, 900)
            assert params == {"temperature": 0.2, "max_completion_tokens": 900}, model

    def test_anthropic_caps_max_tokens(self):
        params = sampling_params("claudeopus5", 99_000)
        assert params["max_tokens"] == ANTHROPIC_MAX_TOKENS

    def test_anthropic_never_sends_both_temperature_and_top_p(self):
        """The table is explicit: pass one or neither, never both."""
        for model in ("claudeopus5", "claudeopus48", "claudesonnet5", "claudehaiku45"):
            params = sampling_params(model, 900)
            assert "top_p" not in params, model
            assert params["max_tokens"] == 900

    def test_other_families_keep_deterministic_temperature(self):
        for model in ("gemini35flash", "gemini31flashlite", "gpt4o"):
            params = sampling_params(model, 900)
            assert params == {"temperature": 0.2, "max_tokens": 900}, model

    def test_gpt4o_is_not_read_as_the_o_series(self):
        """The trailing o in gpt4o is a suffix, not the reasoning series --
        the same shape of homonym trap as REE/rare-earth elsewhere in this repo."""
        assert sampling_params("gpt4o", 900) == {"temperature": 0.2, "max_tokens": 900}

    def test_no_real_argo_id_falls_through_to_the_fallback_by_accident(self):
        """The regression that motivated this rewrite.

        Every id below is one Argo documents as needing something other than
        the default temperature+max_tokens pair. If any of them starts
        producing that pair again, family matching has silently stopped
        working -- which is exactly how the previous bug looked.
        """
        fallback = {"temperature": 0.2, "max_tokens": 900}
        needs_something_else = ("gpto1", "gpto3", "gpto3mini", "gpto4mini",
                                "gpt41", "gpt41mini", "gpt41nano",
                                "gpt5", "gpt5mini", "gpt5nano", "gpt51", "gpt52",
                                "gpt54", "gpt54mini", "gpt55", "gpt56sol", "gpt56luna")
        for model in needs_something_else:
            assert sampling_params(model, 900) != fallback, model


class TestEitherSpellingOfAModelName:
    """Argo takes a model two ways and the client must accept both.

    /v1/models answers in display names ("Claude Sonnet 5", "GPT-5.1"); the API
    documentation's table lists compact ids ("claudesonnet5", "gpt51"). Both
    were sent to the live gateway on 2026-10-20 and both answered, resolving to
    the same build -- so treating either as invalid would reject a working
    configuration for its spelling alone.
    """

    def test_canonical_form_recovers_the_compact_id(self):
        assert canonical_model("GPT-5.1") == "gpt51"
        assert canonical_model("Claude Sonnet 5") == "claudesonnet5"
        assert canonical_model("Gemini 3.5 Flash") == "gemini35flash"

    def test_a_compact_id_is_already_canonical(self):
        for model in ("gpt51", "claudesonnet5", "gemini35flash", "gpto3mini"):
            assert canonical_model(model) == model

    def test_family_is_detected_from_either_spelling(self):
        for display, compact in (("GPT-5.1", "gpt51"),
                                 ("o3-mini", "gpto3mini"),
                                 ("GPT-4.1-nano", "gpt41nano"),
                                 ("Claude Opus 5", "claudeopus5"),
                                 ("Gemini 3.5 Flash", "gemini35flash")):
            assert sampling_params(display, 900) == sampling_params(compact, 900), display

    @staticmethod
    def _models(monkeypatch, ids):
        class R:
            status_code = 200

            def json(self):
                return {"data": [{"id": i} for i in ids]}

            def raise_for_status(self):
                pass

        monkeypatch.setattr(argo.requests, "get", lambda *a, **k: R())

    def test_health_accepts_a_compact_id_against_a_display_name_catalogue(self, monkeypatch):
        """The live catalogue lists display names. Someone following the Argo
        docs writes the compact id. That must not read as 'not available'."""
        self._models(monkeypatch, ["Claude Sonnet 5", "GPT-5.1", "o3-mini"])
        ok, detail = ArgoClient(user="u", model="gpt51").health()
        assert ok, detail
        assert "GPT-5.1" in detail  # says how the catalogue spells it

    def test_health_accepts_a_display_name_too(self, monkeypatch):
        self._models(monkeypatch, ["Claude Sonnet 5", "GPT-5.1"])
        ok, _ = ArgoClient(user="u", model="Claude Sonnet 5").health()
        assert ok

    def test_health_still_catches_a_model_that_is_genuinely_absent(self, monkeypatch):
        self._models(monkeypatch, ["Claude Sonnet 5", "GPT-5.1"])
        ok, detail = ArgoClient(user="u", model="gpt99").health()
        assert not ok and "not among" in detail


class TestTemperatureRefusal:
    """Some Claude models answer 400 "`temperature` is deprecated for this
    model". Verified live: claudesonnet5 refuses it; claudeopus5,
    claudesonnet46 and claudehaiku45 accept it. It is per-model, not
    per-generation, so the name cannot predict it and the client must cope.
    """

    def test_known_refuser_is_not_sent_temperature(self):
        params = sampling_params("claudesonnet5", 900)
        assert "temperature" not in params
        assert params["max_tokens"] == 900

    def test_the_refuser_is_recognised_by_display_name_too(self):
        assert "temperature" not in sampling_params("Claude Sonnet 5", 900)

    def test_other_claude_models_keep_their_temperature(self):
        for model in ("claudeopus5", "claudesonnet46", "claudehaiku45"):
            assert sampling_params(model, 900)["temperature"] == 0.2, model

    def test_a_new_refuser_is_retried_without_temperature(self, monkeypatch):
        """The catalogue moves faster than any list kept in this file, so the
        gateway's own words are taken at face value once, then remembered."""
        sent = []

        class R:
            def __init__(self, status, body, text=""):
                self.status_code, self._body, self.text = status, body, text

            def json(self):
                return self._body

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise argo.requests.HTTPError(f"{self.status_code}")

        def post(url, json=None, **kw):
            sent.append(dict(json))
            if "temperature" in json:
                return R(400, {"error": {"message": "`temperature` is deprecated for this model."}},
                         text='{"message": "`temperature` is deprecated for this model."}')
            return R(200, {"id": "chatcmpl-ok", "usage": {"total_tokens": 9},
                           "choices": [{"finish_reason": "stop",
                                        "message": {"content": "ok"}}]})

        monkeypatch.setattr(argo.requests, "post", post)
        monkeypatch.setattr(argo, "TEMPERATURE_REJECTED", set())
        out = ArgoClient(user="u", model="claudefuture9").chat([{"role": "user", "content": "x"}])

        assert out == "ok"
        assert len(sent) == 2, "should retry exactly once"
        assert "temperature" in sent[0] and "temperature" not in sent[1]
        assert "claudefuture9" in argo.TEMPERATURE_REJECTED, "and remember it"

    def test_an_unrelated_400_is_not_retried(self, monkeypatch):
        """Only the temperature refusal is recoverable; everything else is a
        real error and must surface rather than be silently retried."""
        sent = []

        class R:
            status_code = 400
            text = '{"message": "Invalid model: nope"}'

            def json(self):
                return {"error": {"message": "Invalid model: nope"}}

            def raise_for_status(self):
                raise argo.requests.HTTPError("400")

        def post(url, json=None, **kw):
            sent.append(dict(json))
            return R()

        monkeypatch.setattr(argo.requests, "post", post)
        with pytest.raises(ArgoError, match="Argo request failed"):
            ArgoClient(user="u", model="claudeopus5").chat([{"role": "user", "content": "x"}])
        assert len(sent) == 1

    def test_seeded_refuser_is_a_canonical_spelling(self):
        """Lookup is canonical, so a display name in the set would never hit."""
        for name in TEMPERATURE_REJECTED:
            assert canonical_model(name) == name


class TestConfiguration:
    def test_unconfigured_client_is_not_ready(self, monkeypatch):
        for var in ("ARGO_USER", "ARGO_API_KEY", "ARGO_MODEL"):
            monkeypatch.delenv(var, raising=False)
        assert not ArgoClient().configured()

    def test_legacy_api_key_variable_still_read(self, monkeypatch):
        monkeypatch.delenv("ARGO_USER", raising=False)
        monkeypatch.setenv("ARGO_API_KEY", "someuser")
        monkeypatch.setenv("ARGO_MODEL", "claudesonnet5")
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
        assert not ok and "ARGO_USER" in detail

    def test_model_defaults_so_the_username_is_the_only_required_setting(self, monkeypatch):
        """openai and anthropic both default their model; Argo now matches,
        so a working .env is one line. health() still checks the id is real."""
        monkeypatch.delenv("ARGO_MODEL", raising=False)
        monkeypatch.setenv("ARGO_USER", "someuser")
        client = ArgoClient()
        assert client.model == argo.DEFAULT_ARGO_MODEL
        assert client.configured()

    def test_the_default_model_is_spelled_the_way_the_argo_table_does(self):
        """A default that Argo would reject is worse than none at all. The id
        itself was answered by the live gateway on 2026-10-20; what this guards
        is that nobody later edits it into a display name, which health() would
        still accept but which reads as a typo in the one place users copy from.
        """
        assert canonical_model(argo.DEFAULT_ARGO_MODEL) == argo.DEFAULT_ARGO_MODEL

    def test_the_default_model_gets_the_shape_its_family_requires(self):
        """The default is in the GPT-5.x family, which rejects max_tokens."""
        assert sampling_params(argo.DEFAULT_ARGO_MODEL, 900) == {"max_completion_tokens": 900}

    def test_explicit_model_overrides_the_default(self, monkeypatch):
        monkeypatch.setenv("ARGO_MODEL", "claudeopus5")
        assert ArgoClient(user="u").model == "claudeopus5"

    def test_argo_error_is_an_llm_error(self):
        """So app.py's single `except LLMError` covers the Argo path too."""
        assert issubclass(ArgoError, LLMError)


class TestTruncationDisclosure:
    """Argo is OpenAI-shaped, so it reports a clipped completion as
    finish_reason "length". The README promises all three providers disclose
    truncation; without this the default provider would be the one that
    silently renders a narration cut off where its caveat belonged."""

    @staticmethod
    def _respond(monkeypatch, body):
        class R:
            status_code = 200

            def json(self):
                return body

            def raise_for_status(self):
                pass

        monkeypatch.setattr(argo.requests, "post", lambda *a, **k: R())

    def test_length_finish_reason_is_disclosed(self, monkeypatch):
        self._respond(monkeypatch, {
            "id": "chatcmpl-ok", "usage": {"total_tokens": 900},
            "choices": [{"finish_reason": "length",
                         "message": {"content": "The score cannot distinguish"}}]})
        out = ArgoClient(user="u", model="gpt-4o").chat([{"role": "user", "content": "x"}])
        assert out.startswith("The score cannot distinguish") and "truncated" in out

    def test_complete_answer_is_not_annotated(self, monkeypatch):
        self._respond(monkeypatch, {
            "id": "chatcmpl-ok", "usage": {"total_tokens": 900},
            "choices": [{"finish_reason": "stop", "message": {"content": "A full answer."}}]})
        assert ArgoClient(user="u", model="gpt-4o").chat(
            [{"role": "user", "content": "x"}]) == "A full answer."
