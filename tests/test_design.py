"""Offline tests for rule-based candidate selection.

The reference set is the test fixture on purpose. It holds two real lanthanide
binders and two calcium EF-hand proteins of similar size and fold, which is the
only comparison that can show a rule discriminating rather than merely firing.
"""
import pytest

from lantern.catalog import load_reference
from lantern.chemistry import EF_HAND_HINT, EF_LOOP_INSTRUMENT, ef_hand_loops
from lantern.design import (MAX_ADJACENT_GAP_AA, MAX_LENGTH_AA, MIN_EF_HAND_LOOPS,
                            PASS, FAIL, UNKNOWN, RULES, SELECTION_IS_NOT_AFFINITY,
                            ef_hand_layout, evaluate, rank)
from lantern.models import Protein

LANMODULINS = ("C5B164", "A0A4V2JDD3")      # Mex-LanM, Hans-LanM
CALCIUM_EF_HANDS = ("P0DP23", "P02585")     # calmodulin-1, troponin C
NOT_EF_HANDS = ("P69905", "P00766")         # haemoglobin alpha, chymotrypsinogen A

# A 12-residue loop that matches EF_LOOP_INSTRUMENT: [DN] . {6} [ILV] . {3} E
LOOP = "DAAAAAAIAAAE"


def synthetic(*gaps: int, accession: str = "SYNTH") -> Protein:
    """A protein with len(gaps)+1 EF-hand loops separated by exactly `gaps`."""
    seq = LOOP
    for gap in gaps:
        seq += "G" * gap + LOOP
    return Protein(accession=accession, name="synthetic", organism="none",
                   sequence=seq)


def by_accession(code: str) -> Protein:
    return next(p for p in load_reference() if p.accession == code)


def rule_verdict(record: dict, rule_id: str) -> str:
    return next(row["verdict"] for row in record["rules"] if row["id"] == rule_id)


class TestTheSyntheticFixtureIsWhatItClaims:
    """A fixture that does not have the gaps it says tests nothing."""

    def test_gaps_come_out_as_specified(self):
        assert ef_hand_layout(synthetic(12, 30, 30).sequence)["gaps"] == [12, 30, 30]

    def test_each_spacer_yields_exactly_one_more_loop(self):
        assert ef_hand_layout(synthetic(12, 30, 30).sequence)["count"] == 4
        assert ef_hand_layout(synthetic(20).sequence)["count"] == 2


class TestTheRulesSeparateTheTwoFamilies:

    @pytest.mark.parametrize("code", LANMODULINS)
    def test_both_lanthanide_binders_are_selected(self, code):
        assert evaluate(by_accession(code))["selected"] is True

    @pytest.mark.parametrize("code", CALCIUM_EF_HANDS + NOT_EF_HANDS)
    def test_nothing_else_in_the_reference_set_is(self, code):
        assert evaluate(by_accession(code))["selected"] is False

    @pytest.mark.parametrize("code", CALCIUM_EF_HANDS)
    def test_the_calcium_proteins_are_rejected_on_spacing_and_nothing_else(self, code):
        """Short, four EF-hands, and still not lanmodulins. Spacing is the rule
        earning the answer; if it ever stops being the one that fails, the
        separation shown in the module docstring has moved."""
        record = evaluate(by_accession(code))
        assert rule_verdict(record, "length") == PASS
        assert rule_verdict(record, "ef_hand_count") == PASS
        assert rule_verdict(record, "compact_pair") == FAIL

    def test_the_measured_separation_is_wide_not_marginal(self):
        """12 against 24, either side of a bound of 14."""
        lanm = [ef_hand_layout(by_accession(c).sequence)["min_gap"] for c in LANMODULINS]
        calcium = [ef_hand_layout(by_accession(c).sequence)["min_gap"]
                   for c in CALCIUM_EF_HANDS]
        assert max(lanm) < MAX_ADJACENT_GAP_AA <= min(calcium)
        assert min(calcium) - max(lanm) >= 10

    def test_rank_puts_the_lanthanide_binders_on_top(self):
        result = rank(load_reference(), target="Ce3+")
        assert result["selected_count"] == 2
        assert {c["accession"] for c in result["candidates"][:2]} == set(LANMODULINS)


class TestTheTrapsThisModuleWasBuiltAround:
    """Each of these is a rule that looked right and would have been wrong."""

    def test_counting_with_the_classifier_would_reject_hans_lanm(self):
        """Why ef_hand_count uses the instrument pattern and not the classifier.

        EF_HAND_HINT is tuned to find lanthanide-like loop *chemistry* and
        finds only three of Hans-LanM's four loops. Counting with it fails the
        protein the count exists to find.
        """
        hans = by_accession("A0A4V2JDD3").sequence
        assert len(ef_hand_loops(hans, EF_HAND_HINT)) < MIN_EF_HAND_LOOPS
        assert len(ef_hand_loops(hans, EF_LOOP_INSTRUMENT)) >= MIN_EF_HAND_LOOPS
        assert rule_verdict(evaluate(by_accession("A0A4V2JDD3")),
                            "ef_hand_count") == PASS

    def test_asp_at_position_9_is_not_a_rule(self):
        assert not any("position_9" in rule.id for rule in RULES)

    def test_and_scoring_it_would_have_inverted_the_answer(self):
        """Troponin C carries more Asp at position 9 than Hans-LanM does.

        Hans-LanM, a real lanthanide binder, carries none at all. This is the
        measurement that keeps position 9 an observation.
        """
        hans = evaluate(by_accession("A0A4V2JDD3"))["observations"]["position_9"]
        troponin = evaluate(by_accession("P02585"))["observations"]["position_9"]
        assert hans.get("D", 0) == 0
        assert troponin.get("D", 0) > hans.get("D", 0)

    def test_position_9_is_still_reported_because_it_is_evidence(self):
        observed = evaluate(by_accession("C5B164"))["observations"]
        assert observed["position_9"] == {"D": 4}
        assert "never scored" in observed["position_9_note"]

    def test_one_close_pair_is_enough_not_every_pair(self):
        """The Mattocks criterion is "at least one pair". Reading it as "every
        pair" rejects Hans-LanM, whose own gaps reach the bound."""
        assert evaluate(synthetic(12, 30, 30))["selected"] is True

    def test_but_no_close_pair_at_all_is_a_rejection(self):
        record = evaluate(synthetic(30, 30, 30))
        assert record["selected"] is False
        assert rule_verdict(record, "compact_pair") == FAIL

    def test_the_bound_is_exclusive(self):
        """"fewer than 14" -- 13 passes and 14 does not."""
        assert rule_verdict(evaluate(synthetic(13, 30, 30)), "compact_pair") == PASS
        assert rule_verdict(evaluate(synthetic(14, 30, 30)), "compact_pair") == FAIL


class TestARuleThatCannotBeCheckedIsNotARuleThatPassed:

    @pytest.mark.parametrize("sequence", ["", None, "   ", 42, ["D", "E"]])
    def test_an_unreadable_sequence_gives_unknown_not_pass(self, sequence):
        record = evaluate(Protein(accession="X", name="n", organism="o",
                                  sequence=sequence))
        assert record["selected"] is False
        assert record["passed"] == 0
        assert {row["verdict"] for row in record["rules"]} == {UNKNOWN}

    def test_a_sequence_of_non_amino_acids_is_unknown_too(self):
        record = evaluate(Protein(accession="X", name="n", organism="o",
                                  sequence="DEADBEEF123"))
        assert {row["verdict"] for row in record["rules"]} == {UNKNOWN}
        assert any("not amino acids" in row["detail"] for row in record["rules"])

    def test_the_record_says_which_rule_could_not_be_checked(self):
        record = evaluate(Protein(accession="X", name="n", organism="o"))
        assert len(record["rules"]) == len(RULES)
        assert all(row["detail"] for row in record["rules"])

    def test_fewer_than_two_loops_leaves_the_gap_unmeasured_not_zero(self):
        """`min_gap` of 0 would read as the tightest possible packing."""
        assert ef_hand_layout(LOOP)["min_gap"] is None
        assert ef_hand_layout("")["min_gap"] is None


class TestTheRecordDoesNotOverclaim:

    def test_every_rule_states_its_question_and_its_basis(self):
        for rule in RULES:
            assert rule.question.endswith("?")
            assert len(rule.basis) > 40

    def test_the_mattocks_rules_name_where_they_come_from(self):
        basis = " ".join(rule.basis for rule in RULES)
        assert "Mattocks" in basis and "2023" in basis

    def test_the_disclaimer_denies_affinity_and_ion_specificity(self):
        for phrase in ("not an affinity", "not a selectivity",
                       "not specific to any one lanthanide"):
            assert phrase in SELECTION_IS_NOT_AFFINITY
        assert SELECTION_IS_NOT_AFFINITY in evaluate(by_accession("C5B164"))["disclaimer"]

    def test_every_record_carries_the_disclaimer_including_rejections(self):
        for record in rank(load_reference())["candidates"]:
            assert record["disclaimer"] == SELECTION_IS_NOT_AFFINITY

    def test_the_ordering_says_it_is_not_calibrated(self):
        assert "not a ranking" in rank(load_reference())["ordering"]

    @pytest.mark.parametrize("target", ["Ce3+", "Nd3+", "La3+", "Dy3+"])
    def test_the_target_changes_nothing_and_the_record_admits_it(self, target):
        """Sequence cannot separate one trivalent lanthanide from another, so a
        shortlist that shifted with the target would be inventing the
        difference."""
        baseline = rank(load_reference(), target="Ce3+")
        result = rank(load_reference(), target=target)
        assert result["target"] == target
        assert result["target_was_used"] is False
        assert [c["accession"] for c in result["candidates"]] == \
               [c["accession"] for c in baseline["candidates"]]

    def test_the_gap_definition_travels_with_the_number(self):
        observed = evaluate(by_accession("C5B164"))["observations"]
        assert "12-residue EF-loop" in observed["gap_definition"]

    def test_length_bound_is_the_published_one(self):
        assert (MAX_LENGTH_AA, MIN_EF_HAND_LOOPS, MAX_ADJACENT_GAP_AA) == (200, 4, 14)


class TestRankingIsStable:

    def test_ranking_is_deterministic(self):
        proteins = load_reference()
        first = [c["accession"] for c in rank(proteins)["candidates"]]
        shuffled = list(reversed(proteins))
        assert [c["accession"] for c in rank(shuffled)["candidates"]] == first

    def test_more_rules_passed_always_outranks_fewer(self):
        order = rank(load_reference())["candidates"]
        passed = [c["passed"] for c in order]
        assert passed == sorted(passed, reverse=True)

    def test_an_empty_input_is_an_empty_shortlist_not_an_error(self):
        result = rank([])
        assert result["candidates"] == [] and result["selected_count"] == 0
