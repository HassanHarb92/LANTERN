from reefinder.models import Protein
from reefinder.chemistry import score_sequence, screen
from reefinder.catalog import load_demo
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

def test_demo_never_claims_real_sequence():
    proteins = load_demo()
    assert all("synthetic" in p.source.lower() for p in proteins)

def test_campaign_provenance():
    c = run_campaign()
    assert c["mode"] == "synthetic demo"
    assert all("score_type" in row for row in c["candidates"])
