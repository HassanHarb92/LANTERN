"""Offline tests for retrieval by sequence criteria (M4 step 2 of the independent test pass).

What these pin, and why they exist beyond tests/test_design.py:

* **The spacing boundary.** The Mattocks 2023 rule is "fewer than 14 residues"; the paper's own prose says 12-13. The two readings
  disagree on what to do with a gap of 13 (both pass) and 14 (rule fails, prose also fails) but they diverge on *which proteins*
  they admit once a protein has one short gap and several long ones. The boundary is pinned at 11-15 so a change to either side is loud.
* **Loose versus strict.** `design.py` implements the loose rule (at least one adjacent pair < 14). Measured over 165,902 UniProt
  EF-hand sequences under 200 aa (UniProt 2026_03, 2026-10-20) it admits 2,266 four-loop sequences, against 156 when every gap must be
  12-13. These tests pin that the shipped rule is the loose one, so that choosing the strict one later is a visible, deliberate change.
* **Identity-blindness.** A held-out recovery test is only meaningful if the rules read the sequence and nothing else. If
  `evaluate()` ever began to read the name, organism or an annotation, recovering A0A4V2JDD3 would stop being evidence.
"""
import pytest

from lantern.catalog import load_reference
from lantern.design import FAIL, MAX_ADJACENT_GAP_AA, PASS, ef_hand_layout, evaluate, rank
from lantern.models import Protein

LANMODULINS = ("C5B164", "A0A4V2JDD3")        # Mex-LanM, Hans-LanM
CALCIUM_EF_HANDS = ("P0DP23", "P02585")       # calmodulin-1, troponin C
NEGATIVES = ("P69905", "P00766")              # haemoglobin alpha, chymotrypsinogen A

# A 12-residue loop that matches EF_LOOP_INSTRUMENT: [DN] . {6} [ILV] . {3} E
LOOP = "DAAAAAAIAAAE"


def synthetic(*gaps: int, accession: str = "SYNTH") -> Protein:
    """A protein with len(gaps)+1 EF-hand loops separated by exactly `gaps` residues."""
    seq = LOOP
    for gap in gaps:
        seq += "G" * gap + LOOP
    return Protein(accession=accession, name="synthetic", organism="none", sequence=seq)


def reference(code: str) -> Protein:
    return next(p for p in load_reference() if p.accession == code)


def verdict(record: dict, rule_id: str) -> str:
    return next(row["verdict"] for row in record["rules"] if row["id"] == rule_id)


def strict_every_gap_12_to_13(sequence: str) -> bool:
    """The paper's prose reading: four loops and every adjacent gap is 12 or 13 residues."""
    layout = ef_hand_layout(sequence)
    return layout["count"] == 4 and all(12 <= g <= 13 for g in layout["gaps"])


class TestSpacingBoundary:
    @pytest.mark.parametrize("gap,expected", [(11, PASS), (12, PASS), (13, PASS), (14, FAIL), (15, FAIL)])
    def test_compact_pair_rule_flips_at_exactly_the_bound(self, gap, expected):
        record = evaluate(synthetic(gap, gap, gap))
        assert verdict(record, "compact_pair") == expected

    def test_the_bound_is_fourteen_and_strictly_less(self):
        assert MAX_ADJACENT_GAP_AA == 14
        assert verdict(evaluate(synthetic(13, 13, 13)), "compact_pair") == PASS
        assert verdict(evaluate(synthetic(14, 14, 14)), "compact_pair") == FAIL

    @pytest.mark.parametrize("gap", [11, 12, 13, 14, 15])
    def test_the_measured_gap_equals_the_constructed_gap(self, gap):
        """Guards the definition: gap = residues between the end of one 12-residue loop and the start of the next."""
        assert ef_hand_layout(synthetic(gap, gap, gap).sequence)["gaps"] == [gap, gap, gap]


class TestReferenceSpacingIsPinned:
    """ROADMAP 3.8 table, reproduced from the sequences rather than copied from the prose."""

    @pytest.mark.parametrize("code,gaps", [("C5B164", [12, 13, 12]), ("A0A4V2JDD3", [12, 13, 12])])
    def test_lanmodulin_linkers_are_twelve_to_thirteen(self, code, gaps):
        assert ef_hand_layout(reference(code).sequence)["gaps"] == gaps

    @pytest.mark.parametrize("code,gaps", [("P0DP23", [24, 25, 24]), ("P02585", [24, 28, 24])])
    def test_calcium_ef_hand_linkers_are_twenty_four_or_more(self, code, gaps):
        assert ef_hand_layout(reference(code).sequence)["gaps"] == gaps

    @pytest.mark.parametrize("code", NEGATIVES)
    def test_proteins_without_ef_hands_have_no_gaps_not_zero(self, code):
        layout = ef_hand_layout(reference(code).sequence)
        assert layout["gaps"] == [] and layout["min_gap"] is None


class TestLooseVersusStrict:
    def test_the_shipped_rule_is_the_loose_one(self):
        """One short gap and two long ones passes the shipped rule and fails the paper's prose reading."""
        protein = synthetic(13, 30, 30)
        assert evaluate(protein)["selected"] is True
        assert strict_every_gap_12_to_13(protein.sequence) is False

    def test_the_strict_reading_still_accepts_both_lanmodulins(self):
        for code in LANMODULINS:
            assert strict_every_gap_12_to_13(reference(code).sequence)

    def test_the_strict_reading_still_rejects_both_calcium_proteins(self):
        for code in CALCIUM_EF_HANDS:
            assert not strict_every_gap_12_to_13(reference(code).sequence)

    def test_on_the_reference_set_loose_and_strict_agree_so_the_set_cannot_tell_them_apart(self):
        """Why the difference was invisible: both rules give the same six verdicts here. The 2,266-versus-156
        difference only appears at scale, which is a statement about this fixture's power, not about the rules."""
        for protein in load_reference():
            loose = evaluate(protein)["selected"]
            strict = strict_every_gap_12_to_13(protein.sequence) and len(protein.sequence) < 200
            assert loose == strict, protein.accession


class TestHeldOutRecovery:
    """Recovery of a known binder has to rest on the sequence alone."""

    @pytest.mark.parametrize("code", LANMODULINS)
    def test_verdict_ignores_name_organism_and_accession(self, code):
        original = reference(code)
        scrambled = Protein(accession="ZZZZZZ", name="Calmodulin-1", organism="Homo sapiens",
                            sequence=original.sequence)
        a, b = evaluate(original), evaluate(scrambled)
        assert a["selected"] is b["selected"] is True
        assert [r["verdict"] for r in a["rules"]] == [r["verdict"] for r in b["rules"]]

    @pytest.mark.parametrize("code", CALCIUM_EF_HANDS)
    def test_a_calcium_protein_is_not_rescued_by_a_lanmodulin_label(self, code):
        original = reference(code)
        relabelled = Protein(accession="C5B164", name="Lanmodulin", organism="Methylorubrum extorquens",
                             sequence=original.sequence)
        record = evaluate(relabelled)
        assert record["selected"] is False
        assert verdict(record, "compact_pair") == FAIL

    def test_a_generic_ef_hand_pool_without_any_family_term_recovers_both_controls(self):
        """The reference proteins stand in for a generic EF-hand pool (InterPro IPR011992 carries all of them);
        no family term is available to `rank`, only sequences."""
        pool = [Protein(accession=p.accession, name="EF-hand domain-containing protein", organism="",
                        sequence=p.sequence) for p in load_reference()]
        result = rank(pool)
        selected = {r["accession"] for r in result["candidates"] if r["selected"]}
        assert selected == set(LANMODULINS)
        assert result["considered"] == 6

    def test_selection_is_not_an_affinity_claim(self):
        assert "affinity" in rank(load_reference())["disclaimer"].lower()
