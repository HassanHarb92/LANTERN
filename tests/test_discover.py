"""Offline tests for the whole question-to-structure loop.

Every test here runs with no network and no language model: `answer()` falls
back to the regex parser and the bundled reference set, and the structures
come from `data/structures/`. If any of these start needing a network, the
offline guarantee has been broken somewhere upstream.

The assertions are mostly about what the record REFUSES to say. Each step of
this pipeline is careful on its own; the failure mode of joining them is a
record that is true field by field and misleading read as a whole.
"""
import pytest

from lantern.catalog import load_reference
from lantern.design import SELECTION_IS_NOT_AFFINITY
from lantern.discover import (LANTHANIDE_ELEMENTS, PREDICTION_HAS_NO_METAL,
                              SIZE_MATCH_IS_NOT_BINDING, SIZE_RANK_SELF_CHECK,
                              SPHERE_CLOSED_AROUND_THE_DEPOSITED_ION,
                              _element_of, _rank_of, answer, headline)
from lantern.models import Protein
from lantern.plan import SOURCE_FALLBACK

CANONICAL = "what proteins should I try for capturing Ce3+"
LANMODULINS = {"C5B164", "A0A4V2JDD3"}


@pytest.fixture(scope="module")
def run():
    """The canonical question, answered once and shared. Read-only."""
    return answer(CANONICAL)


def every_site(record):
    return [s for ev in record["evidence"] for s in ev["sites"]]


class TestTheCanonicalQuestionRunsOffline:
    """The user's own example, end to end, with nothing configured."""

    def test_it_answers(self, run):
        assert run["answered"] is True
        assert run["plan"]["target"] == "Ce3+"
        assert run["plan"]["parsed_by"] == SOURCE_FALLBACK

    def test_it_shortlists_exactly_the_two_lanthanide_binders(self, run):
        selected = {c["accession"] for c in run["shortlist"]["candidates"]
                    if c["selected"]}
        assert selected == LANMODULINS

    def test_it_measures_real_sites_from_deposited_coordinates(self, run):
        assert run["evidence"], "no structural evidence was gathered at all"
        assert all(ev["structure_kind"] == "deposited" for ev in run["evidence"])
        assert {ev["pdb_id"] for ev in run["evidence"]} == {"8FNS", "8FNR"}
        assert len(every_site(run)) > 0

    def test_every_measured_site_holds_an_actual_lanthanide(self, run):
        for site in every_site(run):
            assert site["deposited_element"].upper() in LANTHANIDE_ELEMENTS

    def test_the_headline_counts_what_was_actually_measured(self, run):
        assert str(len(every_site(run))) in headline(run)
        assert "Ce3+" in headline(run)


class TestAQuestionThatCannotBeAnsweredIsNotAnswered:
    """`answered: False` has to mean nothing downstream ran."""

    @pytest.mark.parametrize("question", [
        "", "   ", "what proteins are good?", "tell me about proteins",
        "how do I capture uranium?",
    ])
    def test_no_validated_target_means_no_shortlist_and_no_evidence(self, question):
        record = answer(question)
        assert record["answered"] is False
        assert record["shortlist"] is None
        assert record["evidence"] == []

    def test_the_refusal_explains_itself(self):
        record = answer("what proteins are good?")
        assert record["notes"], "a refusal with no notes is a dead end"
        assert "did not resolve" in headline(record)

    def test_a_flagged_plan_is_refused_even_though_it_has_a_target(self):
        """plan.py flags a model-only target. It must not be run anyway.

        This is the join that could quietly undo plan.py's corroboration gate:
        the Plan object carries a usable `target` field, so a caller that
        reads `target` without reading `needs_clarification` runs it.
        """
        class ModelInventingATarget:
            def configured(self):
                return True

            def chat(self, messages, **kwargs):
                return ('{"target": "Nd3+", "competitor": "Ca2+", '
                        '"corpus": "lanmodulin", "limit": 10}')

        record = answer("find me something for the rare earth",
                        client=ModelInventingATarget())
        assert record["plan"]["target"] == "Nd3+"
        assert record["plan"]["needs_clarification"] is True
        assert record["answered"] is False
        assert record["shortlist"] is None


class TestTheShortlistDoesNotBorrowTheTargetsAuthority:
    """The list is architecture-based. Printing it under "for Ce3+" implies
    otherwise, so the record has to deny it in words."""

    def test_the_record_says_the_target_was_not_used(self, run):
        assert run["shortlist"]["target"] == "Ce3+"
        assert run["shortlist"]["target_was_used"] is False

    def test_a_caveat_says_so_in_prose(self, run):
        assert any("does not depend on Ce3+" in c for c in run["caveats"])

    def test_the_affinity_disclaimer_is_always_present(self, run):
        assert SELECTION_IS_NOT_AFFINITY in run["caveats"]

    @pytest.mark.parametrize("target", ["Ce3+", "Nd3+", "La3+", "Dy3+"])
    def test_the_shortlist_is_identical_for_every_target(self, target):
        record = answer(f"what proteins should I try for capturing {target}")
        assert record["plan"]["target"] == target
        assert [c["accession"] for c in record["shortlist"]["candidates"]] == \
               [c["accession"] for c in answer(CANONICAL)["shortlist"]["candidates"]]


class TestTheSizeComparisonIsLabelledAsACounterfactual:
    """8FNS holds neodymium. The user asked about cerium. The record must not
    let those two blur together."""

    def test_the_deposited_element_travels_with_every_number(self, run):
        for site in every_site(run):
            assert site["deposited_element"]

    def test_a_different_element_is_flagged_on_the_site_itself(self, run):
        for site in every_site(run):
            assert site["size_match_is_counterfactual"] is True

    def test_and_in_the_caveats(self, run):
        assert any("not evidence that this protein was observed binding Ce3+" in c
                   for c in run["caveats"])
        assert SPHERE_CLOSED_AROUND_THE_DEPOSITED_ION in run["caveats"]

    def test_the_flag_is_false_when_the_elements_do_match(self):
        """Asking about Nd3+ against the Nd structure is not a counterfactual."""
        record = answer("what proteins should I try for capturing Nd3+")
        nd_sites = [s for ev in record["evidence"] if ev.get("pdb_id") == "8FNS"
                    for s in ev["sites"]]
        assert nd_sites
        assert all(s["size_match_is_counterfactual"] is False for s in nd_sites)

    def test_size_match_caveats_are_attached_whenever_a_fit_is_shown(self, run):
        assert SIZE_MATCH_IS_NOT_BINDING in run["caveats"]


class TestTheSizeScoreCarriesItsOwnCalibration:
    """The self-check that makes the fit readable: where does the score put
    the ion that is demonstrably in the site?"""

    def test_every_site_reports_where_the_deposited_ion_ranked(self, run):
        for site in every_site(run):
            context = site["ion_context"]
            assert "deposited_rank" in context
            assert context["deposited_rank"] is not None \
                or context["deposited_rank_unavailable"]

    def test_the_score_does_not_recover_the_ion_that_is_bound(self, run):
        """The measurement this whole presentation exists because of.

        If a future ion table made the deposited ion rank first everywhere,
        this test fails and the honest move is to re-read SIZE_RANK_SELF_CHECK
        and weaken it -- not to delete the test.
        """
        ranks = [s["ion_context"]["deposited_rank"] for s in every_site(run)]
        placed = [r for r in ranks if r is not None]
        assert placed, "nothing was placed, so the self-check never ran"
        assert max(placed) > 1, "the deposited ion now ranks first everywhere"

    def test_the_self_check_is_stated_where_a_reader_will_meet_it(self, run):
        assert SIZE_RANK_SELF_CHECK in run["caveats"]
        assert all(s["ion_context"]["self_check"] == SIZE_RANK_SELF_CHECK
                   for s in every_site(run))

    def test_an_unplaceable_ion_says_why_instead_of_going_blank(self, run):
        """`deposited_rank: None` rendered as an empty cell reads as "worst"."""
        unplaced = [s for s in every_site(run)
                    if s["ion_context"]["deposited_rank"] is None]
        assert unplaced, "expected the CN-10 site, where Nd is not tabulated"
        for site in unplaced:
            reason = site["ion_context"]["deposited_rank_unavailable"]
            assert "tabulates no radius" in reason or "not a trivalent" in reason

    def test_rank_of_distinguishes_absent_from_last(self):
        ordering = [{"ion": "Gd3+", "fit": 0.9}, {"ion": "Ce3+", "fit": 0.1}]
        assert _rank_of("GD", ordering) == 1
        assert _rank_of("CE", ordering) == 2
        assert _rank_of("CA", ordering) is None
        assert _rank_of("", ordering) is None

    @pytest.mark.parametrize("label,element", [
        ("Ce3+", "CE"), ("ce3+", "CE"), ("Nd3+", "ND"), ("Ca2+", "CA"),
    ])
    def test_element_of_strips_the_charge(self, label, element):
        assert _element_of(label) == element


class TestAnUnmeasurableCandidateIsNotAPassingOne:

    def test_a_candidate_with_no_structure_says_the_number_is_unknown(self):
        """A selected protein with nothing to measure must not look verified."""
        bare = Protein(accession="X1", name="synthetic lanmodulin-like",
                       organism="none",
                       sequence=("DAAAAAAIAAAE" + "G" * 12) * 3 + "DAAAAAAIAAAE")
        record = answer(CANONICAL, proteins=[bare])
        assert record["answered"] is True
        assert record["shortlist"]["selected_count"] == 1
        evidence = record["evidence"][0]
        assert evidence["structure_kind"] == "none"
        assert evidence["sites"] == []
        assert any("unknown" in note for note in evidence["notes"])

    def test_a_linked_structure_that_is_not_cached_is_not_silently_skipped(self):
        absent = Protein(accession="X2", name="n", organism="o", pdb_id="1ABC",
                         sequence=("DAAAAAAIAAAE" + "G" * 12) * 3 + "DAAAAAAIAAAE")
        record = answer(CANONICAL, proteins=[absent], live=False)
        notes = " ".join(record["evidence"][0]["notes"])
        assert "1ABC" in notes and "cache" in notes

    def test_no_prediction_is_attempted_unless_it_is_asked_for(self):
        """allow_predictions defaults off, so this must not touch the network."""
        bare = Protein(accession="C5B164", name="n", organism="o",
                       sequence=("DAAAAAAIAAAE" + "G" * 12) * 3 + "DAAAAAAIAAAE")
        record = answer(CANONICAL, proteins=[bare])
        assert record["evidence"][0]["structure_kind"] == "none"

    def test_the_prediction_disclaimer_denies_a_coordination_number(self):
        for phrase in ("no coordination number", "no size comparison",
                       "not about binding"):
            assert phrase in PREDICTION_HAS_NO_METAL


class TestVerificationCanBeSkippedButNotFaked:

    def test_verify_false_returns_a_shortlist_with_no_evidence(self):
        record = answer(CANONICAL, verify=False)
        assert record["answered"] is True
        assert record["shortlist"]["selected_count"] == 2
        assert record["evidence"] == []

    def test_and_the_headline_does_not_claim_any_sites(self):
        assert "No deposited coordinates" in headline(answer(CANONICAL, verify=False))

    def test_size_match_caveats_are_absent_when_nothing_was_measured(self):
        caveats = answer(CANONICAL, verify=False)["caveats"]
        assert SIZE_MATCH_IS_NOT_BINDING not in caveats
        assert SPHERE_CLOSED_AROUND_THE_DEPOSITED_ION not in caveats

    def test_max_structures_bounds_the_work_without_hiding_the_shortlist(self):
        record = answer(CANONICAL, max_structures=1)
        assert record["shortlist"]["selected_count"] == 2
        assert len(record["evidence"]) == 1


class TestTheRecordIsSelfDescribing:

    def test_every_site_names_itself(self, run):
        """Carried through from the geometry fix: a call must not be
        positionally matched to a site."""
        for site in every_site(run):
            assert site["site_id"]["chain"] == site["chain"]
            assert site["site_id"]["site"] == site["site"]

    def test_the_notes_say_which_corpus_was_screened(self, run):
        assert any("reference set" in note for note in run["notes"])
        assert any(str(len(load_reference())) in note for note in run["notes"])

    def test_the_question_is_echoed_back_verbatim(self):
        assert answer(CANONICAL)["question"] == CANONICAL

    def test_an_asu_negative_call_is_marked_unreliable(self, run):
        """geometry-v2's rule: from an asymmetric unit, only a pass is safe."""
        for site in every_site(run):
            if site["call"] == "calcium-like":
                assert site["call_reliable"] is False
