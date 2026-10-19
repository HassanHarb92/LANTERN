from reefinder.models import Protein
from reefinder.chemistry import score_sequence, screen
from reefinder.catalog import load_reference, load_synthetic
from reefinder.agent import run_campaign

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
