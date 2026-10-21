import json
import random

import pytest

from lantern.critic import lineage as L
from lantern.critic import policy as P
from lantern.critic.policy import FROZEN, PARAM_BOUNDS, Params, apply_to_ranking, decide, evaluate, net_evidence, objective
from lantern.critic.types import Evidence, Verdict


def ev(n, cid=None, lineage=False, preprint=False, score=0.9):
    return Evidence(n=n, cid=cid or f"c{n}", lineage=lineage, preprint=preprint, score=score)


def vd(label, cited, conf=0.8, cid="k"):
    return Verdict(claim_id=cid, label=label, cited=tuple(cited), confidence=conf)


# ---- frozen guard and validation -------------------------------------------------------------------------------
def test_frozen_defaults():
    assert FROZEN.alpha_lineage == 0.3
    assert FROZEN.w_external == 1.0
    assert FROZEN.preprint_discount == 0.8
    assert FROZEN.conf_floor == 0.3
    assert FROZEN.tau_review == 0.5 and FROZEN.tau_badge == 0.5
    assert FROZEN.min_independent == 1


@pytest.mark.parametrize("kw", [
    {"alpha_lineage": -0.1}, {"alpha_lineage": 1.1}, {"w_external": -1}, {"preprint_discount": 0},
    {"preprint_discount": 1.5}, {"tau_review": 0}, {"tau_badge": -1}, {"min_independent": -1},
    {"min_independent": 1.5}, {"min_independent": True}, {"conf_floor": 1.2}, {"relevance_floor": -0.1},
])
def test_validation(kw):
    with pytest.raises(ValueError):
        Params(**kw)


def test_vector_roundtrip_clip_and_length():
    assert Params.names() == list(PARAM_BOUNDS)
    assert "w_external" not in PARAM_BOUNDS
    assert Params.from_vector(FROZEN.to_vector()) == FROZEN
    p = Params(alpha_lineage=0.5, tau_badge=2.0)
    assert Params.from_vector(p.to_vector()) == p
    hi = Params.from_vector([99] * len(PARAM_BOUNDS))
    lo = Params.from_vector([-99] * len(PARAM_BOUNDS))
    for n, (a, b) in PARAM_BOUNDS.items():
        assert getattr(hi, n) == b and getattr(lo, n) == a
    assert hi.w_external == 1.0 and hi.min_independent == 1
    with pytest.raises(ValueError):
        Params.from_vector([0.1])


# ---- weighting -------------------------------------------------------------------------------------------------
def test_alpha_discount_exact():
    v = [vd("supports", [1])]
    ext = net_evidence(v, [ev(1)])["net"]
    lin = net_evidence(v, [ev(1, lineage=True)])["net"]
    assert lin == pytest.approx(0.3 * ext)
    assert net_evidence(v, [ev(1, lineage=True)], Params(alpha_lineage=0.5))["net"] == pytest.approx(0.5 * ext)


def test_lineage_only_never_badges():
    v = [vd("supports", [1, 2, 3], conf=1.0)]
    e = [ev(i, lineage=True) for i in (1, 2, 3)]
    d = decide(v, e, Params(alpha_lineage=1.0, tau_badge=0.05))
    assert d["action"] == "keep" and d["details"]["lineage_only_support"]
    assert "lineage" in d["reason"].lower()
    d0 = decide(v, e, Params(alpha_lineage=1.0, min_independent=0))
    assert d0["action"] == "keep"


def test_external_plus_lineage_badge_rules():
    # one external + many lineage sources in a single verdict: mean weight = (1 + 0.3*4)/5
    e = [ev(1, "ext")] + [ev(i, f"l{i}", lineage=True) for i in range(2, 6)]
    v = [vd("supports", [1, 2, 3, 4, 5], conf=1.0)]
    d = decide(v, e)
    assert d["details"]["net"] == pytest.approx(0.44)
    assert d["details"]["independent_support"] == 1
    assert d["action"] == "keep"  # 0.44 < tau_badge
    assert decide(v, e, Params(tau_badge=0.4))["action"] == "badge"
    assert decide(v, e, Params(tau_badge=0.4, min_independent=2))["action"] == "keep"
    # a lineage-heavy verdict plus a separate external verdict passes
    v2 = [vd("supports", [2, 3], conf=1.0, cid="a"), vd("supports", [1], conf=0.5, cid="b")]
    assert decide(v2, e)["action"] == "badge"


def test_preprint_discount():
    v = [vd("supports", [1], conf=1.0)]
    assert net_evidence(v, [ev(1, preprint=True)])["net"] == pytest.approx(0.8)
    assert net_evidence(v, [ev(1, lineage=True, preprint=True)])["net"] == pytest.approx(0.24)


def test_floors():
    e = [ev(1, score=0.2)]
    low = [vd("supports", [1], conf=0.29)]
    assert net_evidence(low, e)["net"] == 0.0
    assert net_evidence([vd("supports", [1], conf=0.3)], e)["net"] == pytest.approx(0.3)
    assert net_evidence([vd("supports", [1], conf=0.9)], e, Params(relevance_floor=0.5))["net"] == 0.0
    r = net_evidence([vd("supports", [1], conf=0.9)], e, Params(relevance_floor=0.5))
    assert r["independent_support"] == 0


def test_contradiction_demotes():
    d = decide([vd("contradicts", [1], conf=0.9)], [ev(1)])
    assert d["action"] == "review" and d["net"] == pytest.approx(-0.9)
    # lineage-sourced contradiction at 0.3 weight: -0.27 does not demote
    d = decide([vd("contradicts", [1], conf=0.9)], [ev(1, lineage=True)])
    assert d["action"] == "keep"
    # a confident contradiction is a veto even when other claims agree: the net must not hide it
    d = decide([vd("contradicts", [1], conf=0.9), vd("supports", [2], conf=0.9)], [ev(1), ev(2)])
    assert d["action"] == "review" and d["net"] == pytest.approx(0.0)
    many = [vd("supports", [n], conf=0.9) for n in range(2, 11)] + [vd("contradicts", [1], conf=0.9)]
    d = decide(many, [ev(n) for n in range(1, 11)])
    assert d["net"] > 5 and d["action"] == "review"
    # a vetoed candidate is never badged
    assert d["action"] != "badge"


def test_no_evidence_keeps():
    d = decide([vd("no_evidence", [], conf=0.9), vd("no_evidence", [1], conf=0.9)], [ev(1)])
    assert d["action"] == "keep" and d["net"] == 0.0
    assert "absence of papers is not evidence" in d["reason"].lower()
    assert decide([], [])["action"] == "keep"


def test_invalid_citations_contribute_zero():
    d = net_evidence([vd("supports", [7, 8], conf=1.0), vd("supports", [], conf=1.0)], [ev(1)])
    assert d["net"] == 0.0 and d["independent_support"] == 0


def test_actions_closed_set_and_params_in_output():
    d = decide([vd("supports", [1])], [ev(1)])
    assert d["action"] in ("keep", "badge", "review")
    assert d["params"]["alpha_lineage"] == 0.3


# ---- ranking ---------------------------------------------------------------------------------------------------
def test_apply_to_ranking_basic_and_no_mutation():
    cands = [{"accession": "A", "score": 9}, {"accession": "B", "score": 8}, {"accession": "C", "score": 7}]
    snap = json.loads(json.dumps(cands))
    out = apply_to_ranking(cands, {"A": {"action": "review", "reason": "r"}, "C": {"action": "badge", "reason": "b"}})
    assert [c["accession"] for c in out] == ["B", "C", "A"]
    assert out[0]["critic_action"] == "keep" and out[1]["critic_action"] == "badge"
    assert out[2]["critic_reason"] == "r"
    assert cands == snap and all("critic_action" not in c for c in cands)
    assert [c["score"] for c in out] == [8, 7, 9]  # numbers untouched


def test_apply_to_ranking_never_promotes_property():
    rng = random.Random(1234)
    for _ in range(200):
        n = rng.randint(0, 15)
        cands = [{"accession": f"P{i}", "score": rng.random()} for i in range(n)]
        decs = {c["accession"]: {"action": rng.choice(["keep", "badge", "review"]), "reason": "x"}
                for c in cands if rng.random() < 0.8}
        out = apply_to_ranking(cands, decs)
        assert sorted(c["accession"] for c in out) == sorted(c["accession"] for c in cands)
        is_rev = [c["critic_action"] == "review" for c in out]
        assert is_rev == sorted(is_rev)  # all non-review first
        orig = [c["accession"] for c in cands]
        for group in (False, True):
            got = [c["accession"] for c in out if (c["critic_action"] == "review") == group]
            assert got == [a for a in orig if a in set(got)]


# ---- objective -------------------------------------------------------------------------------------------------
def _cases():
    contra = {"verdicts": [vd("contradicts", [1], conf=0.9)], "evidence": [ev(1)], "should_flag": True}
    support = {"verdicts": [vd("supports", [1], conf=0.9)], "evidence": [ev(1)], "should_flag": False}
    none = {"verdicts": [vd("no_evidence", [])], "evidence": [], "should_flag": False}
    return [contra, support, none]


def test_objective_and_evaluate():
    cases = _cases()
    default = FROZEN.to_vector()
    m = evaluate(FROZEN, cases)
    assert (m["tp"], m["fp"], m["fn"], m["tn"]) == (1, 0, 0, 2)
    assert m["precision"] == 1.0 and m["recall"] == 1.0
    assert objective(default, cases) == pytest.approx(0.0)  # perfect, centre: no penalty
    bad = list(default)
    bad[Params.names().index("tau_review")] = 5.0  # never flags -> one false negative
    assert objective(bad, cases) > objective(default, cases)
    inverted = [dict(c, should_flag=not c["should_flag"]) for c in cases]
    assert objective(default, inverted) > objective(default, cases)
    assert objective(default, inverted) == pytest.approx((2 + 2 * 1) / 3)


def test_objective_empty():
    with pytest.raises(ValueError):
        objective(FROZEN.to_vector(), [])


# ---- lineage ---------------------------------------------------------------------------------------------------
def test_doi_extraction():
    t = ("See (doi 10.1021/jacs.1c01234). Also [paper](https://doi.org/10.1038/S41586-020-2649-2), and "
         "**10.1016/S0092-8674(00)81234-5**; plus 10.1002/ANIE.202012345.")
    got = L.lineage_from_text(t)
    assert got == {"10.1021/jacs.1c01234", "10.1038/s41586-020-2649-2", "10.1016/s0092-8674(00)81234-5",
                   "10.1002/anie.202012345"}
    assert L.lineage_from_text("") == set()


def test_is_lineage_normalisation():
    lin = {"10.1021/jacs.1c01234"}
    assert L.is_lineage("https://doi.org/10.1021/JACS.1C01234", lin)
    assert L.is_lineage("10.1021/jacs.1c01234.", lin)
    assert not L.is_lineage("10.1021/other", lin)
    assert not L.is_lineage("", lin)


def test_lineage_from_files_and_load(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "README.md").write_text("cite 10.1/abcd1 and 10.1234/Foo.")
    (tmp_path / "docs" / "SCIENTIFIC_CONTRACT.md").write_text("(10.5555/bar)")
    (tmp_path / "data" / "critic_lineage.json").write_text(json.dumps(["https://doi.org/10.9999/Zed"]))
    extra = tmp_path / "extra.json"
    extra.write_text(json.dumps(["10.7777/extra"]))
    got = L.load_lineage(extra_file=extra, root=tmp_path)
    assert {"10.1234/foo", "10.5555/bar", "10.9999/zed", "10.7777/extra"} <= got
    assert L.lineage_from_files([tmp_path / "nope.md"]) == set()


def test_load_lineage_missing_files(tmp_path):
    assert L.load_lineage(extra_file=tmp_path / "missing.json", root=tmp_path / "nowhere") == set()
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "critic_lineage.json").write_text("not json")
    assert L.load_lineage(root=tmp_path) == set()
    assert isinstance(L.load_lineage(), set)  # real repo root works
