"""Offline tests for query construction. No network access."""
import pytest
from lantern import uniprot
from lantern.uniprot import (ALLOWED_QUERIES, FIELDS, INTERPRO_FAMILIES, TOPICS,
                             choose_structure, pdb_cross_references,
                             search_proteins)

# The shape UniProt actually returns, captured from a live call for C5B164 on
# 2026-10-20 and trimmed. Written out rather than mocked loosely, because the
# bug this guards was a field that was never requested: a fixture invented
# from the docstring would have described a response the API does not send.
C5B164 = {
    "primaryAccession": "C5B164",
    "proteinDescription": {"recommendedName": {"fullName": {"value": "Lanmodulin"}}},
    "organism": {"scientificName": "Methylorubrum extorquens"},
    "sequence": {"value": "MSSHHHH"},
    "uniProtKBCrossReferences": [
        {"database": "PDB", "id": "6MI5", "properties": [
            {"key": "Method", "value": "NMR"},
            {"key": "Resolution", "value": "-"},
            {"key": "Chains", "value": "X=23-133"}]},
        {"database": "PDB", "id": "8FNS", "properties": [
            {"key": "Method", "value": "X-ray"},
            {"key": "Resolution", "value": "1.01 A"},
            {"key": "Chains", "value": "A=29-133"}]},
        {"database": "AlphaFoldDB", "id": "C5B164", "properties": []},
    ],
}


def xray(pdb_id: str, resolution_A: float) -> dict:
    return {"id": pdb_id, "method": "X-ray", "resolution_A": resolution_A,
            "chains": "A=1-100"}


def nmr(pdb_id: str) -> dict:
    return {"id": pdb_id, "method": "NMR", "resolution_A": None,
            "chains": "A=1-100"}


class TestASearchResultCarriesItsStructures:
    """The live search used to strip them. A hit arrived with pdb_id None, so
    discover reported "no deposited structure and no prediction, so the
    coordination number is unknown" for lanmodulin itself -- while UniProt was
    cross-referencing 8FNS at 1.01 A in the same record, and the offline path
    was measuring that very file. Turning on live search silently cost the
    user the half of the platform that measures anything."""

    def test_the_query_asks_for_the_cross_references(self):
        """Parsing them is moot if the field is never requested: UniProt omits
        uniProtKBCrossReferences entirely unless xref_pdb is in `fields`."""
        assert "xref_pdb" in FIELDS.split(",")

    def test_a_hit_arrives_with_a_structure_to_measure(self):
        protein = uniprot._to_protein(C5B164, source="test", notes="")
        assert protein.pdb_id == "8FNS", (
            "a live hit with no pdb_id reaches discover as 'no deposited "
            "structure', which is the bug")
        assert len(protein.pdb_options) == 2

    def test_only_pdb_cross_references_are_read(self):
        """The same block carries AlphaFoldDB, EMDB and others; an accession
        from one of those is not a PDB id and would 404 on fetch."""
        assert [o["id"] for o in pdb_cross_references(C5B164)] == ["6MI5", "8FNS"]

    def test_an_entry_with_no_structures_is_not_an_error(self):
        bare = {"primaryAccession": "A0A089NZ72", "sequence": {"value": "MK"}}
        protein = uniprot._to_protein(bare, source="test", notes="")
        assert protein.pdb_id is None and protein.pdb_options == []


class TestWhichStructureGetsMeasured:
    """One is measured and the rest are not, so the rule has to be stated and
    has to be stable -- the same search twice must not measure two different
    structures and report two different coordination numbers."""

    def test_the_sharpest_structure_is_measured(self):
        chosen, reason = choose_structure([xray("1ABC", 2.80), xray("2DEF", 1.40)])
        assert chosen == "2DEF"
        assert "1.4" in reason and "2 structure" in reason

    def test_a_structure_stating_no_resolution_is_not_ranked_against_one_that_does(self):
        """None means "this entry states none", the same answer
        resolution_from_coordinates gives for NMR. Treated as a number it
        would sort either first or last; neither is a measurement."""
        chosen, _ = choose_structure([nmr("6MI5"), xray("8FNS", 2.90)])
        assert chosen == "8FNS"

    def test_when_nothing_states_a_resolution_the_choice_says_it_is_arbitrary(self):
        chosen, reason = choose_structure([nmr("2XYZ"), nmr("1ABC")])
        assert chosen == "1ABC"
        assert "arbitrary" in reason, (
            "an id-order fallback presented as a rule reads like a judgement")

    def test_the_same_options_choose_the_same_structure_twice(self):
        options = [xray("2DEF", 1.40), xray("1ABC", 1.40)]
        assert choose_structure(options)[0] == choose_structure(options[::-1])[0]

    def test_the_reason_says_resolution_is_not_relevance(self):
        """Resolution is about how far to trust the geometry call. A
        cross-reference does not say which metal is in which file, so the
        sharpest structure is not necessarily the one holding the user's ion."""
        _, reason = choose_structure([xray("1ABC", 2.80), xray("2DEF", 1.40)])
        assert "not a judgement" in reason

    def test_no_structures_yields_no_claim(self):
        assert choose_structure([]) == (None, "")


@pytest.mark.parametrize("value,expected", [
    ("1.01 A", 1.01), ("2.30 A", 2.30), ("-", None), ("", None), (None, None)])
def test_resolution_is_parsed_or_honestly_absent(value, expected):
    assert uniprot._resolution(value) == expected


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
