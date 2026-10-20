"""Offline tests for AlphaFold DB retrieval and the pLDDT gate. No network access.

`requests.get` is stubbed at the module boundary, the way tests/test_argo.py
stubs `argo.requests`, so nothing here touches alphafold.ebi.ac.uk. The payload
the stub returns is a trimmed copy of the real one observed on 2026-10-20 for
C5B164, field names included -- a fixture invented from the docstring would
pass against code that misread the API.
"""
import json
from pathlib import Path

import pytest

from lantern import alphafold
from lantern.alphafold import (EVIDENCE, GATE_MINIMUM_PLDDT, MODEL_CACHE,
                               NOT_SCORED, PLDDT_CONFIDENT, PLDDT_LOW,
                               PLDDT_VERY_HIGH, SCORABLE,
                               SIDECHAIN_RELIABLE_PLDDT, AlphaFoldError,
                               AlphaFoldUnavailable, MalformedPrediction,
                               NoModelAvailable, NotAPredictedModel,
                               confidence_band,
                               confidence_gate, cached_model, fetch_model,
                               mean_plddt, prediction_metadata, residue_plddt,
                               site_confidence, valid_accession,
                               withhold_if_unconfident)

ROOT = Path(__file__).resolve().parent.parent

# Field-for-field a trimmed copy of the live response for C5B164 (Mex-LanM)
# retrieved on 2026-10-20, so the parser is tested against the API's real
# spelling -- globalMetricValue, latestVersion, pdbUrl, fractionPlddt* and all.
C5B164_PAYLOAD = {
    "toolUsed": "AlphaFold Monomer v2.0 pipeline",
    "entityType": "protein",
    "isUniProt": True,
    "modelEntityId": "AF-C5B164-F1",
    "modelCreatedDate": "2025-08-01T00:00:00Z",
    "globalMetricValue": 83.94,
    "fractionPlddtVeryLow": 0.105,
    "fractionPlddtLow": 0.113,
    "fractionPlddtConfident": 0.15,
    "fractionPlddtVeryHigh": 0.632,
    "latestVersion": 6,
    "allVersions": [2, 3, 4, 5, 6],
    "sequence": "MAFRLSSAVLLAALVAAPAYA",
    "uniprotAccession": "C5B164",
    "uniprotId": "LANM_METEA",
    "uniprotDescription": "Lanmodulin",
    "organismScientificName": "Methylorubrum extorquens",
    "chainId": "A",
    "cifUrl": "https://alphafold.ebi.ac.uk/files/AF-C5B164-F1-model_v6.cif",
    "pdbUrl": "https://alphafold.ebi.ac.uk/files/AF-C5B164-F1-model_v6.pdb",
    "isComplex": False,
    "entryId": "AF-C5B164-F1",
}


BACKBONE = (("N", "N"), ("CA", "C"), ("C", "C"), ("O", "O"))


def atom_line(serial: int, name: str, element: str, chain: str,
              number: int, plddt: float) -> str:
    """One ATOM record in AlphaFold DB's exact column layout.

    Copied column for column from a real file so Bio.PDB reads these the way
    it reads the real thing:
    `ATOM      1  N   MET A   1      29.092  21.830 -82.489  1.00 47.06    N`
    """
    return (f"ATOM  {serial:5d} {name:^4s} ALA {chain}{number:4d}    "
            f"{float(serial):8.3f}{0.0:8.3f}{0.0:8.3f}{1.0:6.2f}{plddt:6.2f}"
            f"          {element:>2s}")


def model_pdb(plddt_by_residue: dict[int, float], chain: str = "A",
              atoms=BACKBONE) -> str:
    """A minimal AlphaFold-shaped PDB with pLDDT in the B-factor column."""
    lines = ["HEADER                                            01-AUG-25",
             "TITLE     ALPHAFOLD MONOMER V2.0 PREDICTION FOR TEST"]
    serial = 1
    for number in sorted(plddt_by_residue):
        for name, element in atoms:
            lines.append(atom_line(serial, name, element, chain, number,
                                   plddt_by_residue[number]))
            serial += 1
    lines.append("END")
    return "\n".join(lines) + "\n"


class FakeResponse:
    """The slice of requests.Response this module touches."""

    def __init__(self, status_code=200, payload=None, text="", bad_json=False):
        self.status_code = status_code
        self._payload = payload
        self.text = text
        self._bad_json = bad_json

    def json(self):
        if self._bad_json:
            raise ValueError("Expecting value: line 1 column 1 (char 0)")
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise alphafold.requests.HTTPError(str(self.status_code))


def stub_get(monkeypatch, *, api=None, model_text=None, counter=None):
    """Route the API call and the file download through one fake requests.get."""
    def get(url, **kwargs):
        if counter is not None:
            counter.append(url)
        if "/api/prediction/" in url:
            return api if api is not None else FakeResponse(payload=[C5B164_PAYLOAD])
        return FakeResponse(text=model_text if model_text is not None else "")

    monkeypatch.setattr(alphafold.requests, "get", get)


@pytest.fixture
def mex_lanm_model():
    """pLDDT values whose residue-level mean rounds to the 83.94 the API reports.

    Twenty residues at 83.94 exactly; the point is the agreement check in
    `_record`, not a reproduction of the real 133-residue profile.
    """
    return model_pdb({n: 83.94 for n in range(1, 21)})


class TestSuccessfulFetch:
    """A retrieved model, labelled as a prediction and nothing more."""

    def test_a_successful_fetch_returns_a_cached_file_and_its_provenance(
            self, monkeypatch, tmp_path, mex_lanm_model):
        stub_get(monkeypatch, model_text=mex_lanm_model)
        record = fetch_model("C5B164", cache_dir=tmp_path)

        assert record["accession"] == "C5B164"
        assert record["entry_id"] == "AF-C5B164-F1"
        assert record["model_version"] == 6
        assert record["model_created"] == "2025-08-01T00:00:00Z"
        assert record["source_url"].endswith("AF-C5B164-F1-model_v6.pdb")
        assert Path(record["model_path"]).exists()
        assert Path(record["model_path"]).parent == tmp_path

    def test_mean_plddt_comes_from_the_api_and_is_cross_checked_against_the_file(
            self, monkeypatch, tmp_path, mex_lanm_model):
        """globalMetricValue is the authoritative figure -- it is what the
        database publishes -- but a file that disagrees with it means the cache
        and the metadata describe different models, so both are reported."""
        stub_get(monkeypatch, model_text=mex_lanm_model)
        record = fetch_model("C5B164", cache_dir=tmp_path)

        assert record["mean_plddt"] == 83.94
        assert record["mean_plddt_from_file"] == 83.94
        assert "globalMetricValue" in record["mean_plddt_source"]
        assert record["mean_plddt_band"] == "confident"

    def test_published_band_fractions_are_carried_through(
            self, monkeypatch, tmp_path, mex_lanm_model):
        """A mean of 83.94 hides that 10.5% of this entry is very low."""
        stub_get(monkeypatch, model_text=mex_lanm_model)
        fractions = fetch_model("C5B164", cache_dir=tmp_path)["plddt_band_fractions"]
        assert fractions == {"very_low": 0.105, "low": 0.113,
                             "confident": 0.15, "very_high": 0.632}

    def test_a_lowercase_accession_is_accepted_and_normalised(
            self, monkeypatch, tmp_path, mex_lanm_model):
        """The live API answers `c5b164`; rejecting a shift key is not science."""
        stub_get(monkeypatch, model_text=mex_lanm_model)
        assert fetch_model("c5b164", cache_dir=tmp_path)["accession"] == "C5B164"


class TestTheRecordIsLabelledAPrediction:
    """The project distinguishes experimental from computational evidence
    everywhere. A model from AlphaFold DB is computational, was not run here,
    and must never read as a deposited structure."""

    def test_the_record_says_it_is_not_experimental(
            self, monkeypatch, tmp_path, mex_lanm_model):
        stub_get(monkeypatch, model_text=mex_lanm_model)
        record = fetch_model("C5B164", cache_dir=tmp_path)
        assert record["experimental"] is False
        assert record["evidence"] == EVIDENCE

    def test_the_evidence_string_says_predicted_retrieved_and_not_run_here(self):
        text = EVIDENCE.lower()
        assert "predicted" in text and "retrieved" in text
        assert "alphafold db" in text
        assert "not an experimental structure" in text
        assert "not run here" in text

    def test_no_string_in_the_module_claims_alphafold_was_executed(self):
        """Guards the wording, which is the whole contract of this module.

        "we ran alphafold" in a caveat or a reason would reach a user verbatim.
        """
        source = (ROOT / "lantern" / "alphafold.py").read_text().lower()
        for claim in ("we ran alphafold", "ran alphafold2", "we predict",
                      "alphafold was run", "running alphafold"):
            assert claim not in source, claim

    def test_predicted_models_are_cached_apart_from_experimental_ones(self):
        """data/structures/ holds deposited coordinates and is committed.
        Predicted models go to the gitignored .cache/, so neither directory can
        hand out the other kind of file and nothing large enters git."""
        from lantern.structure import STRUCTURE_CACHE

        assert MODEL_CACHE != STRUCTURE_CACHE
        assert MODEL_CACHE.parent.name == ".cache"
        assert ".cache/" in (ROOT / ".gitignore").read_text().splitlines()


class TestFailClosed:
    """404, network failure and malformed JSON each raise. None of them may
    produce a record that downstream ranking could read as a real model."""

    def test_a_404_raises_no_model_available(self, monkeypatch, tmp_path):
        """P62158 answers 404 live: it is a demerged calmodulin accession, so
        this is a routine answer about a real protein, not a service fault."""
        stub_get(monkeypatch, api=FakeResponse(status_code=404, payload={}))
        with pytest.raises(NoModelAvailable, match="no predicted model"):
            fetch_model("P62158", cache_dir=tmp_path)

    def test_a_network_failure_raises_unavailable_not_no_model(
            self, monkeypatch, tmp_path):
        """"We could not ask" and "there is no model" are different facts and
        must not collapse into one verdict about the protein."""
        def boom(url, **kwargs):
            raise alphafold.requests.ConnectionError("name resolution failed")

        monkeypatch.setattr(alphafold.requests, "get", boom)
        with pytest.raises(AlphaFoldUnavailable, match="unreachable"):
            fetch_model("C5B164", cache_dir=tmp_path)

    def test_malformed_json_raises(self, monkeypatch, tmp_path):
        stub_get(monkeypatch, api=FakeResponse(bad_json=True))
        with pytest.raises(MalformedPrediction, match="unparseable JSON"):
            fetch_model("C5B164", cache_dir=tmp_path)

    def test_an_empty_result_list_is_no_model_not_an_empty_record(
            self, monkeypatch, tmp_path):
        stub_get(monkeypatch, api=FakeResponse(payload=[]))
        with pytest.raises(NoModelAvailable, match="empty result"):
            fetch_model("C5B164", cache_dir=tmp_path)

    @pytest.mark.parametrize("body", [{}, {"error": "try later"}, "", 0])
    def test_an_undocumented_body_is_malformed_not_a_claim_that_no_model_exists(
            self, monkeypatch, tmp_path, body):
        """Shape is checked before emptiness, and the order is the point.

        `if not payload` ran first, so a 200 carrying `{}` -- an error
        envelope, or a schema change -- raised "AlphaFold DB returned an empty
        result for C5B164: no model". That is a definite claim about the
        protein, made on the strength of a response the module did not
        understand. "The service said something unexpected" is the true one.
        """
        stub_get(monkeypatch, api=FakeResponse(payload=body))
        with pytest.raises(MalformedPrediction, match="documented schema"):
            fetch_model("C5B164", cache_dir=tmp_path)

    def test_a_non_404_http_error_raises_unavailable(self, monkeypatch, tmp_path):
        stub_get(monkeypatch, api=FakeResponse(status_code=503, payload={}))
        with pytest.raises(AlphaFoldUnavailable, match="HTTP 503"):
            fetch_model("C5B164", cache_dir=tmp_path)

    def test_a_missing_required_field_raises(self, monkeypatch, tmp_path):
        payload = {k: v for k, v in C5B164_PAYLOAD.items() if k != "globalMetricValue"}
        stub_get(monkeypatch, api=FakeResponse(payload=[payload]))
        with pytest.raises(MalformedPrediction, match="globalMetricValue"):
            fetch_model("C5B164", cache_dir=tmp_path)

    def test_a_record_with_no_coordinate_url_raises(self, monkeypatch, tmp_path):
        payload = {k: v for k, v in C5B164_PAYLOAD.items()
                   if k not in ("pdbUrl", "cifUrl")}
        stub_get(monkeypatch, api=FakeResponse(payload=[payload]))
        with pytest.raises(MalformedPrediction, match="neither pdbUrl nor cifUrl"):
            fetch_model("C5B164", cache_dir=tmp_path)

    def test_multiple_entries_are_refused_rather_than_taking_the_first(
            self, monkeypatch, tmp_path):
        """A multi-entry payload is a fragmented or complex model. Scoring
        entry [0] would silently score a fragment as the whole protein."""
        stub_get(monkeypatch, api=FakeResponse(payload=[C5B164_PAYLOAD, C5B164_PAYLOAD]))
        with pytest.raises(MalformedPrediction, match="2 entries"):
            fetch_model("C5B164", cache_dir=tmp_path)

    def test_a_record_for_the_wrong_accession_is_refused(self, monkeypatch, tmp_path):
        stub_get(monkeypatch,
                 api=FakeResponse(payload=[{**C5B164_PAYLOAD,
                                            "uniprotAccession": "P0DP23"}]))
        with pytest.raises(MalformedPrediction, match="says P0DP23"):
            fetch_model("C5B164", cache_dir=tmp_path)

    def test_coordinates_with_no_atom_records_are_refused(
            self, monkeypatch, tmp_path):
        """A 200 carrying an error page would otherwise parse to zero residues
        and a confidently wrong mean pLDDT."""
        stub_get(monkeypatch, model_text="<html>503 Service Unavailable</html>")
        with pytest.raises(MalformedPrediction, match="no coordinate records"):
            fetch_model("C5B164", cache_dir=tmp_path)

    def test_a_file_disagreeing_with_its_metadata_is_refused(
            self, monkeypatch, tmp_path):
        """The stale-cache bug: a coordinate file left over from an earlier
        model version paired with fresh metadata is a plausible wrong answer."""
        stub_get(monkeypatch, model_text=model_pdb({n: 41.0 for n in range(1, 11)}))
        with pytest.raises(MalformedPrediction, match="different models"):
            fetch_model("C5B164", cache_dir=tmp_path)

    def test_an_unreachable_model_file_raises_even_though_the_api_answered(
            self, monkeypatch, tmp_path):
        def get(url, **kwargs):
            if "/api/prediction/" in url:
                return FakeResponse(payload=[C5B164_PAYLOAD])
            raise alphafold.requests.Timeout("read timed out")

        monkeypatch.setattr(alphafold.requests, "get", get)
        with pytest.raises(AlphaFoldUnavailable, match="could not be downloaded"):
            fetch_model("C5B164", cache_dir=tmp_path)

    def test_every_failure_is_one_module_specific_error(self):
        """So a caller can write one `except AlphaFoldError` and know nothing
        slipped past as a requests exception."""
        for error in (NoModelAvailable, AlphaFoldUnavailable, MalformedPrediction):
            assert issubclass(error, AlphaFoldError)


class TestAccessionValidation:
    def test_a_malformed_accession_is_rejected_before_any_request(self, monkeypatch):
        def no_network(*args, **kwargs):
            raise AssertionError("must not reach the network")

        monkeypatch.setattr(alphafold.requests, "get", no_network)
        for bad in ("", "lanmodulin", "C5B164X", "'; DROP TABLE", "AF-C5B164-F1"):
            with pytest.raises(ValueError, match="UniProt accession"):
                prediction_metadata(bad)

    def test_real_accessions_from_this_project_are_accepted(self):
        """Six- and ten-character forms, both of which UniProt issues."""
        for accession in ("C5B164", "A0A4V2JDD3", "P0DP23", "P02585", "Q1H2G7"):
            assert valid_accession(accession.lower()) == accession


class TestCaching:
    def test_the_cache_prevents_a_second_network_call(
            self, monkeypatch, tmp_path, mex_lanm_model):
        urls = []
        stub_get(monkeypatch, model_text=mex_lanm_model, counter=urls)

        first = fetch_model("C5B164", cache_dir=tmp_path)
        assert len(urls) == 2, "one API call plus one file download"

        monkeypatch.setattr(alphafold.requests, "get", lambda *a, **k:
                            (_ for _ in ()).throw(AssertionError("network used")))
        second = fetch_model("C5B164", cache_dir=tmp_path)
        assert second == first

    def test_use_cache_false_re_fetches(self, monkeypatch, tmp_path, mex_lanm_model):
        """AlphaFold DB re-releases entries -- C5B164 is on v6 with v2-v5 still
        listed -- so a pinned cache can fall behind and must be overridable."""
        urls = []
        stub_get(monkeypatch, model_text=mex_lanm_model, counter=urls)
        fetch_model("C5B164", cache_dir=tmp_path)
        fetch_model("C5B164", cache_dir=tmp_path, use_cache=False)
        assert len(urls) == 4

    def test_cached_model_returns_none_when_nothing_was_fetched(self, tmp_path):
        assert cached_model("C5B164", cache_dir=tmp_path) is None

    def test_metadata_without_its_coordinate_file_is_a_miss_not_a_record(
            self, monkeypatch, tmp_path, mex_lanm_model):
        """Half a cache entry must not be served as a model."""
        stub_get(monkeypatch, model_text=mex_lanm_model)
        record = fetch_model("C5B164", cache_dir=tmp_path)
        Path(record["model_path"]).unlink()
        assert cached_model("C5B164", cache_dir=tmp_path) is None

    def test_unparseable_cached_metadata_raises_rather_than_being_ignored(
            self, tmp_path):
        (tmp_path / "C5B164.json").write_text("{not json")
        with pytest.raises(MalformedPrediction, match="not valid JSON"):
            cached_model("C5B164", cache_dir=tmp_path)

    def test_an_incomplete_cached_record_raises_a_module_error_not_a_key_error(
            self, monkeypatch, tmp_path, mex_lanm_model):
        """A hand-edited or truncated cache must still be covered by a caller's
        single `except AlphaFoldError`."""
        stub_get(monkeypatch, model_text=mex_lanm_model)
        fetch_model("C5B164", cache_dir=tmp_path)
        stored = json.loads((tmp_path / "C5B164.json").read_text())
        del stored["globalMetricValue"]
        (tmp_path / "C5B164.json").write_text(json.dumps(stored))

        with pytest.raises(MalformedPrediction, match="globalMetricValue"):
            cached_model("C5B164", cache_dir=tmp_path)

    def test_cached_metadata_of_the_wrong_shape_raises(self, tmp_path):
        (tmp_path / "C5B164.json").write_text("[]")
        with pytest.raises(MalformedPrediction, match="not a prediction record"):
            cached_model("C5B164", cache_dir=tmp_path)

    def test_a_record_filed_under_the_wrong_accession_is_refused(
            self, tmp_path, mex_lanm_model):
        """The cache is where a mixed-up accession becomes permanent.

        prediction_metadata() checks the fetch path, but it is the cache that
        persists: a C5B164.json holding A0A4V2JDD3's record would answer every
        later call about C5B164 with the wrong protein's model, forever, with
        no network request to notice it. Nothing downstream re-checks, so the
        check has to be here.
        """
        (tmp_path / "AF-C5B164-F1-model_v6.pdb").write_text(mex_lanm_model)
        impostor = {**C5B164_PAYLOAD, "uniprotAccession": "A0A4V2JDD3",
                    "_lantern_model_file": "AF-C5B164-F1-model_v6.pdb"}
        (tmp_path / "C5B164.json").write_text(json.dumps(impostor))
        with pytest.raises(MalformedPrediction, match="filed under C5B164"):
            cached_model("C5B164", cache_dir=tmp_path)

    def test_the_matching_accession_still_loads(self, tmp_path, mex_lanm_model):
        (tmp_path / "AF-C5B164-F1-model_v6.pdb").write_text(mex_lanm_model)
        good = {**C5B164_PAYLOAD, "_lantern_model_file": "AF-C5B164-F1-model_v6.pdb"}
        (tmp_path / "C5B164.json").write_text(json.dumps(good))
        assert cached_model("C5B164", cache_dir=tmp_path)["accession"] == "C5B164"

    def test_the_cached_metadata_is_the_api_payload_plus_the_filename(
            self, monkeypatch, tmp_path, mex_lanm_model):
        stub_get(monkeypatch, model_text=mex_lanm_model)
        fetch_model("C5B164", cache_dir=tmp_path)
        stored = json.loads((tmp_path / "C5B164.json").read_text())
        assert stored["globalMetricValue"] == 83.94
        assert stored["_lantern_model_file"] == "AF-C5B164-F1-model_v6.pdb"


class TestAnExperimentalStructureIsRefused:
    """The highest-stakes guard in the module.

    `residue_plddt` reads the B-factor column. In an AlphaFold model that
    column is pLDDT; in a crystal structure it is a temperature factor, with
    the same units-free look and a comparable magnitude. Before this guard,
    `mean_plddt("data/structures/8FNS.pdb")` returned a number -- the mean
    B-factor of a 1.01 A X-ray structure -- and `site_confidence` would
    cheerfully gate on it and emit a "confidence verdict" about measured
    coordinates. The failure is silent, plausible, and scientifically void.

    These run against the real committed entries, not a synthetic file,
    because the point is that actual experimental data is rejected.
    """

    EXPERIMENTAL = ["8FNS.pdb", "9PI2.pdb", "1CLL.pdb", "8DQ2.pdb", "8FNR.pdb"]

    @pytest.mark.parametrize("name", EXPERIMENTAL)
    def test_residue_plddt_refuses_a_measured_structure(self, name):
        path = ROOT / "data" / "structures" / name
        assert path.exists(), name
        with pytest.raises(NotAPredictedModel):
            residue_plddt(path)

    @pytest.mark.parametrize("name", EXPERIMENTAL)
    def test_every_public_reader_refuses_it_too(self, name):
        """Three entry points share the column; all three must share the guard."""
        path = ROOT / "data" / "structures" / name
        with pytest.raises(NotAPredictedModel):
            mean_plddt(path)
        with pytest.raises(NotAPredictedModel):
            site_confidence(path, [20, 21])

    def test_the_refusal_is_catchable_as_the_module_s_existing_error(self):
        """NotAPredictedModel subclasses MalformedPrediction, so a caller
        written before this guard existed still handles it."""
        assert issubclass(NotAPredictedModel, MalformedPrediction)
        assert issubclass(NotAPredictedModel, AlphaFoldError)
        with pytest.raises(AlphaFoldError):
            residue_plddt(ROOT / "data" / "structures" / "8FNS.pdb")

    def test_a_file_with_no_alphafold_marker_is_refused_even_if_b_is_constant(
            self, tmp_path):
        """The two checks are independent, and this is the one that catches a
        grouped-B refinement -- an experimental file whose B-factors ARE
        constant per residue and which the structural test alone would pass."""
        text = model_pdb({1: 80.0, 2: 85.0})
        stripped = "\n".join(line for line in text.splitlines()
                             if "ALPHAFOLD" not in line) + "\n"
        path = tmp_path / "grouped_b.pdb"
        path.write_text(stripped)
        with pytest.raises(NotAPredictedModel, match="no AlphaFold marker"):
            residue_plddt(path)

    def test_b_factors_that_vary_within_a_residue_are_refused(self, tmp_path):
        """The invariant the docstring always claimed and never enforced.

        A file can carry the AlphaFold title and still not have pLDDT in the
        B column -- a re-refined or hand-edited model. pLDDT is one number per
        residue, written to every atom, so disagreement between a residue's
        atoms means this column is something else.
        """
        lines = ["TITLE     ALPHAFOLD MONOMER V2.0 PREDICTION FOR TEST",
                 atom_line(1, "N", "N", "A", 1, 80.0),
                 atom_line(2, "CA", "C", "A", 1, 41.5),   # same residue, different B
                 atom_line(3, "C", "C", "A", 1, 80.0),
                 "END"]
        path = tmp_path / "varying.pdb"
        path.write_text("\n".join(lines) + "\n")
        with pytest.raises(NotAPredictedModel, match="disagree on"):
            residue_plddt(path)

    def test_b_factors_outside_the_plddt_range_are_refused(self, tmp_path):
        """pLDDT is a percentage. A B-factor of 120 is not one."""
        path = tmp_path / "wide.pdb"
        path.write_text(model_pdb({1: 80.0, 2: 120.0}))
        with pytest.raises(NotAPredictedModel, match="not pLDDT"):
            residue_plddt(path)

    def test_a_real_alphafold_file_still_reads(self, tmp_path):
        """The guard must not cost the module its actual job."""
        path = tmp_path / "AF-X-F1-model_v6.pdb"
        path.write_text(model_pdb({1: 47.06, 2: 40.59, 3: 96.12}))
        assert residue_plddt(path) == {1: 47.06, 2: 40.59, 3: 96.12}


class TestReadingPlddtFromTheFile:
    """AlphaFold DB writes per-residue pLDDT into the B-factor column, the same
    value on every atom of a residue. Verified on AF-C5B164-F1-model_v6.pdb:
    all 133 residues carry a constant B, and the series is identical value for
    value to the entry's own AF-C5B164-F1-confidence_v6.json confidenceScore
    array."""

    def test_b_factors_are_read_as_per_residue_plddt(self, tmp_path):
        path = tmp_path / "model.pdb"
        path.write_text(model_pdb({1: 47.06, 2: 40.59, 3: 96.12}))
        assert residue_plddt(path) == {1: 47.06, 2: 40.59, 3: 96.12}

    def test_mean_plddt_is_the_residue_mean_not_the_atom_mean(self, tmp_path):
        """For the real C5B164 model the residue mean is 83.9453, against the
        published globalMetricValue of 83.94; the atom mean is 84.2173, a
        quarter of a point out, because residues differ in atom count and an
        atom mean therefore weights large side chains more heavily.

        Forced here by giving residue 2 four extra side-chain atoms: 4 atoms at
        50.0 and 8 at 90.0 give an atom mean of 76.67 against a residue mean of
        70.0, so a test that passed on both would prove nothing.
        """
        path = tmp_path / "model.pdb"
        sidechain = [atom_line(900 + i, name, "C", "A", 2, 90.0)
                     for i, name in enumerate(("CB", "CG", "CD", "CE"))]
        path.write_text(model_pdb({1: 50.0, 2: 90.0}).replace(
            "END", "\n".join(sidechain) + "\nEND"))

        counts = {r.id[1]: len(list(r))
                  for r in next(alphafold._parse_model(path).get_models())["A"]}
        assert counts == {1: 4, 2: 8}, "the two residues must differ in atom count"
        assert mean_plddt(path) == pytest.approx(70.0)      # residue mean
        assert mean_plddt(path) != pytest.approx(76.667, abs=0.01)  # not the atom mean

    def test_a_missing_file_raises(self, tmp_path):
        with pytest.raises(MalformedPrediction, match="No coordinate file"):
            residue_plddt(tmp_path / "absent.pdb")

    def test_a_multi_chain_file_is_refused(self, tmp_path):
        """Flattening two chains into one residue-number space would let
        chain B's residue 37 overwrite chain A's."""
        path = tmp_path / "complex.pdb"
        path.write_text(model_pdb({1: 90.0}, chain="A").replace("END", "")
                        + model_pdb({1: 40.0}, chain="B"))
        with pytest.raises(MalformedPrediction, match="chains"):
            residue_plddt(path)


class TestConfidenceBands:
    """Band edges are EBI's (very high > 90, confident 90-70, low 70-50, very
    low < 50), from the EMBL-EBI AlphaFold course. The half-open bins below
    reproduce the four fraction fields AlphaFold DB publishes for C5B164
    (0.105 / 0.113 / 0.150 / 0.632) exactly from that model's 133 residues, so
    they are the database's own edges and not a guess."""

    def test_the_cutoffs_are_the_documented_ones(self):
        assert (PLDDT_VERY_HIGH, PLDDT_CONFIDENT, PLDDT_LOW) == (90.0, 70.0, 50.0)

    @pytest.mark.parametrize("value, band", [
        (97.12, "very_high"),   # highest residue in the real C5B164 model
        (90.31, "very_high"),   # lowest residue the API files as category H
        (90.0, "very_high"),
        (89.56, "confident"),   # highest residue filed as category M
        (70.0, "confident"),
        (69.94, "low"),         # highest residue filed as category L
        (51.50, "low"),
        (50.0, "low"),
        (48.56, "very_low"),    # highest residue filed as category D
        (36.41, "very_low"),    # lowest residue in the real C5B164 model
    ])
    def test_observed_values_land_in_the_band_alphafold_db_files_them_under(
            self, value, band):
        assert confidence_band(value) == band


class TestTheConfidenceGate:
    """ROADMAP M4: "Gate on local pLDDT: a low-confidence region yields
    not_scored, not a low score." These two verdicts are different claims and
    the gate exists to keep them apart."""

    def test_a_confident_region_is_scorable(self):
        gate = confidence_gate([91.0, 88.2, 75.5, 70.1])
        assert gate["verdict"] == SCORABLE and gate["scorable"] is True
        assert gate["min_plddt"] == 70.1

    def test_a_low_confidence_region_is_not_scored_rather_than_scored_low(self):
        """The distinction the milestone is written around: no number is
        returned at all, and the reason says so in words a reader will see."""
        gate = confidence_gate([91.0, 88.2, 42.0])
        assert gate["verdict"] == NOT_SCORED and gate["scorable"] is False
        assert gate["verdict"] != 0 and gate["verdict"] is not None
        assert "not the same as scored low" in gate["reason"]
        assert gate["worst_band"] == "very_low"

    def test_the_two_sides_of_the_cutoff_differ_only_in_verdict(self):
        """Just above and just below GATE_MINIMUM_PLDDT, nothing else changed."""
        assert confidence_gate([80.0, GATE_MINIMUM_PLDDT])["scorable"] is True
        assert confidence_gate([80.0, GATE_MINIMUM_PLDDT - 0.1])["scorable"] is False

    def test_one_disordered_residue_sinks_a_region_with_a_high_mean(self):
        """The criterion is the worst residue, not the mean. Four very-high
        donors cannot vouch for a fifth at pLDDT 35: the coordination number
        counted around it is fiction, and the mean is precisely the statistic
        that cannot see it."""
        gate = confidence_gate([96.0, 95.0, 94.0, 93.0, 35.0])
        assert gate["mean_plddt"] > GATE_MINIMUM_PLDDT
        assert gate["verdict"] == NOT_SCORED
        assert gate["residues_below_minimum"] == 1

    def test_an_empty_region_is_not_scored_not_a_pass(self):
        """No residues is no evidence, and the fail-closed reading of no
        evidence is refusal."""
        gate = confidence_gate([])
        assert gate["verdict"] == NOT_SCORED and gate["mean_plddt"] is None
        assert "not a low score" in gate["reason"]

    def test_clearing_the_gate_does_not_claim_reliable_side_chains(self):
        """EBI reserves accurate side chains for pLDDT > 90, and geometry-v2
        counts side-chain carboxylate oxygens. Passing at 70 makes a region
        eligible to be scored, not its donor distances trustworthy."""
        gate = confidence_gate([88.0, 75.0])
        assert gate["scorable"] is True
        assert gate["side_chains_reliable"] is False
        assert any(str(int(SIDECHAIN_RELIABLE_PLDDT)) in c for c in gate["caveats"])

    def test_a_very_high_region_is_marked_side_chain_reliable(self):
        assert confidence_gate([95.0, 92.3])["side_chains_reliable"] is True

    def test_the_gate_never_returns_a_numeric_score(self):
        """It reports confidence. Emitting a score here would recreate the very
        conflation it exists to prevent."""
        for values in ([], [20.0], [95.0, 92.0]):
            assert "score" not in confidence_gate(values)

    def test_every_gate_result_carries_the_apo_caveat(self):
        """An AlphaFold model of a LanM homolog has no metal in it, so any site
        called on one is a hypothesis (ROADMAP risk register)."""
        for values in ([], [95.0], [30.0]):
            assert any("apo" in c for c in confidence_gate(values)["caveats"])


class TestSiteConfidence:
    """"Local pLDDT" in M4 means the residues of the site, not the chain: a
    homolog can average 83 and still hold its fourth EF-hand in a disordered
    stretch."""

    @pytest.fixture
    def model(self, tmp_path):
        path = tmp_path / "AF-TEST-F1-model_v6.pdb"
        path.write_text(model_pdb({35: 95.0, 37: 94.0, 39: 93.0,
                                   41: 92.0, 46: 38.0}))
        return path

    def test_a_confident_site_is_scorable_while_the_chain_mean_is_not_consulted(
            self, model):
        gate = site_confidence(model, [35, 37, 39, 41])
        assert gate["verdict"] == SCORABLE
        assert gate["residues"] == {35: 95.0, 37: 94.0, 39: 93.0, 41: 92.0}

    def test_one_disordered_donor_makes_the_whole_site_not_scored(self, model):
        """Residues 35/37/39/41/46 are 8FNS's real Nd donor set. With 46 at
        pLDDT 38 the site's coordination number is not measurable, so it is
        withheld rather than reported as a weak site."""
        gate = site_confidence(model, [35, 37, 39, 41, 46])
        assert gate["verdict"] == NOT_SCORED
        assert gate["mean_plddt"] > GATE_MINIMUM_PLDDT, "and the mean would have hidden it"

    def test_a_residue_absent_from_the_model_raises_rather_than_being_skipped(
            self, model):
        """Skipping would shrink the site to whichever residues happen to be
        confident -- the most flattering possible gate."""
        with pytest.raises(MalformedPrediction, match=r"\[200\]"):
            site_confidence(model, [35, 200])


class TestWithholdIfUnconfident:
    """One place that enforces the M4 rule, so no caller has to remember it."""

    def test_a_passing_gate_returns_the_score_with_its_confidence_attached(self):
        out = withhold_if_unconfident(confidence_gate([95.0, 93.0]),
                                      {"call": "lanthanide-like", "score": 100.0})
        assert out["call"] == "lanthanide-like" and out["score"] == 100.0
        assert out["confidence"]["verdict"] == SCORABLE

    def test_a_failing_gate_withholds_the_score_instead_of_zeroing_it(self):
        out = withhold_if_unconfident(confidence_gate([95.0, 30.0]),
                                      {"call": "lanthanide-like", "score": 100.0})
        assert out["call"] == NOT_SCORED
        assert out["score"] is None and out["score_withheld"] is True
        assert out["score"] != 0

    def test_the_withheld_record_says_why_and_stays_labelled_a_prediction(self):
        out = withhold_if_unconfident(confidence_gate([30.0]), {"score": 100.0})
        assert "not_scored" in out["reason"]
        assert out["evidence"] == EVIDENCE

    @pytest.mark.parametrize("values", [[95.0, 93.0], [95.0, 30.0]])
    def test_both_paths_carry_the_prediction_labels(self, values):
        """The labels were on the wrong result.

        Only the *withheld* record used to be stamped evidence/experimental.
        The passing record -- the one that gets ranked, charted and handed to
        the narrator -- carried neither, so the single most important fact
        about it (these coordinates were predicted, not measured) was present
        exactly where nobody would act on it and absent where they would.
        """
        out = withhold_if_unconfident(confidence_gate(values), {"score": 100.0})
        assert out["evidence"] == EVIDENCE
        assert out["experimental"] is False

    def test_a_score_that_brought_its_own_evidence_keeps_it(self):
        """A structure-derived score passed through the gate must not have its
        provenance overwritten with AlphaFold's."""
        out = withhold_if_unconfident(
            confidence_gate([95.0, 93.0]),
            {"score": 100.0, "evidence": "X-ray 1.01 A (8FNS)", "experimental": True})
        assert out["evidence"] == "X-ray 1.01 A (8FNS)"
        assert out["experimental"] is True
