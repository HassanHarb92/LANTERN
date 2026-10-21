"""The critic end to end, offline: a real discovery record, a scripted judge, a tiny literature index.

What these pin down is the contract, not the model: the critic may comment and may move a contradicted candidate behind the
others; it may never change a number, promote a candidate, or run when it has nothing to run on.
"""
import copy
import re
from functools import partial

import pytest

from lantern.critic.claims import claims_from_record
from lantern.critic.pipeline import critique
from lantern.critic.policy import FROZEN, Params
from lantern.discover import answer
from lantern.llm import LLMError
from lantern.scholarbud import BM25Index
from lantern.scholarbud.types import Paper

QUESTION = "proteins for capturing Ce3+"
EXTERNAL = Paper(doi="10.1000/external.1", title="Lanthanide coordination number in EF-hand lanmodulin sites",
                 abstract="Lanthanide ions bind lanmodulin EF-hand loops with a high coordination number of oxygen "
                          "donors, and calcium sites show a lower coordination number.", year=2023, source="crossref")
LINEAGE = Paper(doi="10.1000/lineage.1", title="Lanthanide coordination number in EF-hand lanmodulin loops",
                abstract="Lanthanide ions bind lanmodulin EF-hand loops with a high coordination number of oxygen "
                         "donors, and calcium sites show a lower coordination number.", year=2018, source="crossref")


class ScriptedJudge:
    """A judge that labels every claim the same way, citing the first passage it was shown for that claim."""
    model = "scripted"

    def __init__(self, label="supports", only_text=None):
        self.label, self.only_text, self.calls = label, only_text, 0

    def configured(self):
        return True

    def health(self):
        return True, "ok"

    def chat(self, messages, max_tokens=900):
        self.calls += 1
        user = messages[-1]["content"]
        out = []
        for m in re.finditer(r"Claim (c\d+) \(\w+\): (.*?)\n.*?\n\[(\d+)\]", user, re.S):
            cid, text, n = m.group(1), m.group(2), int(m.group(3))
            hit = self.only_text is None or self.only_text in text
            out.append({"claim_id": cid, "label": self.label if hit else "no_evidence",
                        "cited": [n] if hit else [], "confidence": 0.9 if hit else 0.0,
                        "rationale": "The passage addresses the claim." if hit else ""})
        import json
        return json.dumps({"verdicts": out})


class BrokenJudge(ScriptedJudge):
    def chat(self, messages, max_tokens=900):
        self.calls += 1
        raise LLMError("gateway down")


@pytest.fixture(scope="module")
def record():
    return answer(QUESTION)


def _index(*papers):
    return BM25Index(list(papers))


def _numbers(rec):
    return [(e["accession"], s["site"], s["coordination_number"], s["mean_donor_distance_A"])
            for e in rec["evidence"] for s in e["sites"]]


class TestWhenTheCriticCannotRun:
    def test_no_index_leaves_the_record_alone(self, record):
        out = critique(record, ScriptedJudge(), None, lineage=set())
        assert out["critic"]["ran"] is False and out["critic"]["skipped"] == "no literature index"
        assert _numbers(out) == _numbers(record)

    def test_no_client_leaves_the_record_alone(self, record):
        out = critique(record, None, _index(EXTERNAL), lineage=set())
        assert out["critic"]["ran"] is False and "judge" in out["critic"]["skipped"]

    def test_unanswered_record_has_no_claims(self):
        out = critique({"answered": False, "shortlist": None, "evidence": []}, ScriptedJudge(), _index(EXTERNAL),
                       lineage=set())
        assert out["critic"]["ran"] is False and out["critic"]["skipped"] == "no claims"

    def test_a_failing_judge_degrades_to_keep(self, record):
        out = critique(record, BrokenJudge(), _index(EXTERNAL), lineage=set())
        assert all(v["label"] == "no_evidence" for v in out["critic"]["verdicts"])
        assert all(d["action"] == "keep" for d in out["critic"]["decisions"].values())
        assert [c["accession"] for c in out["shortlist"]["candidates"]] == \
               [c["accession"] for c in record["shortlist"]["candidates"]]

    def test_no_matching_literature_means_no_verdicts_and_keep(self, record):
        judge = ScriptedJudge()
        out = critique(record, judge, _index(Paper(doi="10.1/x", title="Perovskite solar cells", abstract="efficiency")),
                       lineage=set())
        assert judge.calls == 0
        assert all(d["action"] == "keep" for d in out["critic"]["decisions"].values())


class TestTheCriticNeverTouchesTheResult:
    def test_numbers_and_input_record_unchanged(self, record):
        before = copy.deepcopy(record)
        out = critique(record, ScriptedJudge("contradicts"), _index(EXTERNAL), lineage=set())
        assert record == before                      # input not mutated
        assert _numbers(out) == _numbers(record)     # measured values identical
        assert out["caveats"] == record["caveats"]

    def test_supports_never_promotes(self, record):
        out = critique(record, ScriptedJudge("supports"), _index(EXTERNAL), lineage=set())
        assert [c["accession"] for c in out["shortlist"]["candidates"]] == \
               [c["accession"] for c in record["shortlist"]["candidates"]]

    def test_contradiction_demotes_only_the_contradicted_protein(self, record):
        claims = claims_from_record(record)
        target = next(c for c in claims if c.kind == "number")
        judge = ScriptedJudge("contradicts", only_text=target.text)
        out = critique(record, judge, _index(EXTERNAL), lineage=set(),
                       params=Params(tau_review=0.1))
        cands = out["shortlist"]["candidates"]
        flagged = [c["accession"] for c in cands if c["critic_action"] == "review"]
        assert flagged, "the contradicted claim should flag its protein"
        order = [c["accession"] for c in cands]
        unflagged = [a for a in order if a not in flagged]
        assert order == unflagged + flagged          # review goes last
        assert unflagged == [a for a in (c["accession"] for c in record["shortlist"]["candidates"]) if a in unflagged]


class TestLineageIsDiscounted:
    def test_independent_support_can_badge(self, record):
        out = critique(record, ScriptedJudge("supports"), _index(EXTERNAL), lineage=set())
        assert any(d["action"] == "badge" for d in out["critic"]["decisions"].values())

    def test_lineage_only_support_never_badges(self, record):
        out = critique(record, ScriptedJudge("supports"), _index(LINEAGE), lineage={LINEAGE.doi})
        assert out["critic"]["ran"] is True
        assert all(d["action"] != "badge" for d in out["critic"]["decisions"].values())
        assert any(e["lineage"] for es in out["critic"]["evidence"].values() for e in es)

    def test_lineage_weight_is_alpha(self, record):
        ext = critique(record, ScriptedJudge("supports"), _index(EXTERNAL), lineage=set())
        lin = critique(record, ScriptedJudge("supports"), _index(LINEAGE), lineage={LINEAGE.doi})
        for acc, d in ext["critic"]["decisions"].items():
            assert lin["critic"]["decisions"][acc]["details"]["net"] == pytest.approx(
                d["details"]["net"] * FROZEN.alpha_lineage / FROZEN.w_external, rel=1e-6)


class TestTheHook:
    def test_answer_accepts_a_critic(self):
        rec = answer(QUESTION, critic=partial(critique, client=ScriptedJudge(), index=_index(EXTERNAL), lineage=set()))
        assert rec["critic"]["ran"] is True and rec["answered"] is True

    def test_default_has_no_critic(self, record):
        assert "critic" not in record

    def test_record_is_json_serialisable(self, record):
        import json
        out = critique(record, ScriptedJudge(), _index(EXTERNAL), lineage=set())
        json.dumps(out)
