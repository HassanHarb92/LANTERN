import inspect

from reefinder.models import Protein
from reefinder.chemistry import (EF_HAND_HINT, EF_LOOP_INSTRUMENT,
                                 ef_hand_loops, score_sequence, screen)
from reefinder.catalog import load_reference, load_synthetic
from reefinder.agent import run_campaign

# Loops read off deposited coordinates by scripts/loop_detector.py, which
# derives them from the lowest-numbered protein donor of each metal site
# rather than transcribing them. EF4 of each lanmodulin is the calcium-like
# one (CN 7, one water) and is included deliberately.
LANTHANIDE_LOOPS = [
    "DPDKDGTIDLKE", "DPDKDGTLDAKE", "DPDNDGTLDKKE", "NPDNDGTIDARE",  # 8FNS
    "NKDNDDSLEIAE", "NPDGDTTLESGE", "NKDGDQTLEMDE", "DANKDGKLTAAE",  # 8FNR/8DQ2
    "NKDGDQTLEIPE", "NPDGDTTLEPDE", "NKDGDQTLELDE", "DKNKDGKLTAKE",  # 9PI2
]
# Calmodulin's four, the canonical calcium arrangement.
CALCIUM_LOOPS = ["DKDGDGTITTKE", "DADGNGTIDFPE",
                 "DKDGNGYISAAE", "DIDGDGQVNYEE"]

def test_scoring_deterministic():
    p = Protein("a", "test", "test", "ADDEDDEDE" * 4)
    assert score_sequence(p).score == score_sequence(p).score

def test_invalid_sequence_is_safe():
    p = Protein("x", "invalid", "none", "")
    assert score_sequence(p).score == 0

def test_screen_sorted():
    seqs = [Protein("a", "acidic", "test", "DE" * 20),
            Protein("b", "nonacidic", "test", "AG" * 20)]
    assert screen(seqs)[0].protein.name == "acidic"

def test_synthetic_set_never_claims_to_be_real():
    # The original guarantee, kept pointed at the synthetic file now that the
    # default screening set is authentic. Fixture data must still say so.
    proteins = load_synthetic()
    assert proteins
    assert all("synthetic" in p.source.lower() for p in proteins)

def test_reference_set_is_labelled_authentic_not_synthetic():
    # The converse guarantee: real sequences must never be labelled synthetic,
    # or the UI would understate its own evidence.
    proteins = load_reference()
    assert proteins
    assert all("synthetic" not in p.source.lower() for p in proteins)
    assert all(p.accession for p in proteins)

def test_campaign_provenance():
    c = run_campaign()
    assert c["mode"] == "curated reference set"
    assert all("score_type" in row for row in c["candidates"])


# --- the classifier and the instrument must not drift into each other ------

def test_the_classifier_is_biased_and_the_instrument_is_not():
    """The whole point of keeping two patterns, pinned as numbers.

    EF_HAND_HINT exists to discriminate, so it should find lanthanide loops
    and miss calcium ones. EF_LOOP_INSTRUMENT exists to measure, so it should
    find both at comparable rates. If either stops behaving that way the
    separation has collapsed and every loop statistic downstream is suspect.
    """
    def recall(pattern, loops):
        return sum(1 for x in loops if pattern.fullmatch(x)) / len(loops)

    classifier_gap = (recall(EF_HAND_HINT, LANTHANIDE_LOOPS)
                      - recall(EF_HAND_HINT, CALCIUM_LOOPS))
    instrument_gap = (recall(EF_LOOP_INSTRUMENT, LANTHANIDE_LOOPS)
                      - recall(EF_LOOP_INSTRUMENT, CALCIUM_LOOPS))
    assert classifier_gap > 0.5, "classifier stopped discriminating"
    assert abs(instrument_gap) < 0.2, "instrument acquired a family bias"
    assert recall(EF_LOOP_INSTRUMENT, CALCIUM_LOOPS) == 1.0


def test_scoring_never_uses_the_measuring_instrument():
    """A guard against the single most likely future mistake.

    The instrument has far better recall, so swapping it in would look like
    an improvement and would silently destroy the discrimination the score
    depends on. Checked structurally, not by behaviour, because the failure
    mode is someone editing score_sequence to 'fix' its poor recall.
    """
    source = inspect.getsource(score_sequence)
    assert "EF_LOOP_INSTRUMENT" not in source
    # And the default really is the classifier.
    assert inspect.signature(ef_hand_loops).parameters["pattern"].default \
        is EF_HAND_HINT


def test_both_patterns_span_exactly_the_twelve_residue_loop():
    # Position indexing in ef_hand_loops() assumes this for either pattern.
    for pattern in (EF_HAND_HINT, EF_LOOP_INSTRUMENT):
        for loop in LANTHANIDE_LOOPS + CALCIUM_LOOPS:
            match = pattern.search(loop)
            if match:
                assert len(match.group(0)) == 12, pattern.pattern


def test_instrument_finds_all_four_calmodulin_loops_and_classifier_does_not():
    """The concrete case the roadmap states: 1 of calmodulin's 4."""
    calmodulin = {p.accession: p for p in load_reference()}["P0DP23"].sequence
    assert len(ef_hand_loops(calmodulin, EF_LOOP_INSTRUMENT)) == 4
    assert len(ef_hand_loops(calmodulin)) == 1
