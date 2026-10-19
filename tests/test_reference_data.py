"""Integrity and provenance tests for the authentic reference set (M1).

These sequences are real, so the tests guard two different things: that the
data has not silently changed under us (checksums), and that the code never
describes it more confidently than the evidence supports (provenance).

The ranking test is deliberately a *regression pin on known-wrong behaviour*,
not an acceptance test. See ROADMAP.md 3.1, 3.6 and the M1 correction note.
"""
import hashlib
import json

import pytest

from reefinder.catalog import (REFERENCE_PATH, SYNTHETIC_PATH, load_reference,
                               load_synthetic, provenance)
from reefinder.chemistry import screen

REFERENCE = {p.accession: p for p in load_reference()}
PROVENANCE = provenance()


def test_reference_set_has_the_six_expected_accessions():
    assert set(REFERENCE) == {"C5B164", "A0A4V2JDD3", "P0DP23", "P02585",
                              "P69905", "P00766"}


def test_every_sequence_matches_its_recorded_checksum():
    # Catches an edited or truncated sequence, which would silently change
    # every score downstream.
    checksums = PROVENANCE["sequence_sha256"]
    assert len(checksums) == len(REFERENCE)
    for accession, protein in REFERENCE.items():
        digest = hashlib.sha256(protein.sequence.encode()).hexdigest()
        assert digest == checksums[accession], f"{accession} sequence changed"


def test_sequences_are_plausible_protein_sequences():
    for accession, protein in REFERENCE.items():
        assert protein.sequence, accession
        assert set(protein.sequence) <= set("ACDEFGHIKLMNPQRSTVWY"), accession


def test_provenance_records_retrieval_date_and_source():
    assert PROVENANCE["source"] == "UniProtKB REST API"
    assert PROVENANCE["retrieved"]
    assert PROVENANCE["record_count"] == len(REFERENCE)
    assert "heuristic" in PROVENANCE["warning"].lower()


def test_roles_cover_positives_negatives_and_the_calcium_contrast():
    roles = PROVENANCE["roles"]
    assert roles["C5B164"] == "lanthanide binder"
    assert roles["A0A4V2JDD3"] == "lanthanide binder"
    # The calcium pair is the discriminating contrast, not filler.
    assert roles["P0DP23"] == "calcium protein"
    assert roles["P02585"] == "calcium protein"
    assert roles["P69905"] == "true negative"
    assert roles["P00766"] == "true negative"


def test_curated_display_names_are_flagged_as_curated():
    # A0A4V2JDD3 is an unreviewed entry whose submitted name is the generic
    # "EF-hand domain-containing protein". We display a curated name, and the
    # record must admit that rather than implying UniProt calls it lanmodulin.
    records = json.loads(REFERENCE_PATH.read_text())["proteins"]
    by_accession = {r["accession"]: r for r in records}
    hans = by_accession["A0A4V2JDD3"]
    assert hans["name_is_curated"] is True
    assert hans["name"] != hans["uniprot_name"]
    assert all(r["uniprot_name"] for r in records)
    # Everything not curated must match its database name exactly.
    for record in records:
        if not record["name_is_curated"]:
            assert record["name"] == record["uniprot_name"], record["accession"]


def test_reference_and_synthetic_sets_are_disjoint():
    # A synthetic sequence leaking into the authentic set would be the single
    # worst failure this project could ship.
    reference_sequences = {p.sequence for p in load_reference()}
    synthetic_sequences = {p.sequence for p in load_synthetic()}
    assert not (reference_sequences & synthetic_sequences)


def test_synthetic_file_declares_itself_tests_only():
    payload = json.loads(SYNTHETIC_PATH.read_text())
    assert "test" in json.dumps(payload["_provenance"]).lower()


def test_ranking_is_non_degenerate():
    scored = screen(load_reference())
    assert len({round(c.score, 1) for c in scored}) == len(scored)


def test_true_negatives_rank_last():
    # The one ordering guarantee the current heuristic does earn.
    ranked = [c.protein.accession for c in screen(load_reference())]
    assert set(ranked[-2:]) == {"P69905", "P00766"}


@pytest.mark.xfail(reason="ROADMAP 3.6: the EF-hand regex requires Asp at loop "
                          "position 1 and Gly at 6; all three Dy3+ loops of "
                          "A0A4V2JDD3 have Asn and non-Gly, so it scores 0 "
                          "motifs. M3 owns the fix.",
                   strict=True)
def test_both_lanthanide_binders_outrank_both_calcium_proteins():
    """The criterion M1 was originally specified to assert.

    It is marked strict-xfail rather than deleted: it is the acceptance test
    for M3, and strict mode means it will fail loudly the moment the descriptor
    is fixed, forcing the marker off and the milestone closed honestly.
    """
    scores = {c.protein.accession: c.score for c in screen(load_reference())}
    worst_lanthanide = min(scores["C5B164"], scores["A0A4V2JDD3"])
    best_calcium = max(scores["P0DP23"], scores["P02585"])
    assert worst_lanthanide > best_calcium


def test_the_inversion_is_pinned_until_m3_fixes_it():
    """Documents the measured defect so a change in it cannot pass unnoticed."""
    scored = {c.protein.accession: c for c in screen(load_reference())}
    hans = scored["A0A4V2JDD3"]
    # Zero motifs despite three structurally confirmed Dy3+ sites in 8FNR.
    assert hans.motif_count == 0
    # And consequently ranked below both calcium proteins.
    assert hans.score < scored["P0DP23"].score
    assert hans.score < scored["P02585"].score
    # But still above the true negatives, so the signal is not pure noise.
    assert hans.score > scored["P69905"].score
