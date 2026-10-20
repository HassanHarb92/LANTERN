"""Offline tests for query construction. No network access."""
import pytest
from lantern import uniprot
from lantern.uniprot import ALLOWED_QUERIES, INTERPRO_FAMILIES, TOPICS, search_proteins


def test_endocytosis_keyword_is_not_queried():
    # KW-0254 is the UniProt keyword for Endocytosis, not EF-hand. Wired as the
    # "ef-hand" option it returned 755 irrelevant proteins. Asserted against the
    # queries themselves, so the comment explaining the removal can survive.
    assert all("KW-0254" not in q for q in ALLOWED_QUERIES.values())
    assert "ef-hand" not in TOPICS


def test_lanmodulin_family_is_offered():
    assert "lanm-family" in INTERPRO_FAMILIES
    assert INTERPRO_FAMILIES["lanm-family"] == ("ncbifam", "NF053806")


def test_family_is_routed_through_interpro_not_uniprot():
    # UniProt records no NCBIfam cross-reference for lanmodulins, so
    # xref:ncbifam-NF053806 returns nothing; membership must come from InterPro.
    assert "lanm-family" not in ALLOWED_QUERIES
    assert all("ncbifam" not in q.lower() for q in ALLOWED_QUERIES.values())


def test_topics_cover_both_retrieval_routes():
    assert set(TOPICS) == set(ALLOWED_QUERIES) | set(INTERPRO_FAMILIES)


@pytest.mark.parametrize("topic", ["ef-hand", "", "'; DROP TABLE", "unknown"])
def test_unknown_topics_rejected_before_any_request(topic):
    with pytest.raises(ValueError, match="Allowed topics"):
        search_proteins(topic)


def test_accession_batches_stay_within_url_limits():
    # 189 accessions in one GET would overrun practical URL length.
    assert uniprot._ACCESSION_BATCH <= 50
