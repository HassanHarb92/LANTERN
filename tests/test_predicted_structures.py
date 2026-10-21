"""Offline tests for predicted structures from sources other than AlphaFold DB (design decision DD-001: ESMFold).

Two kinds of test live here, and the difference matters:

* **Current-behaviour tests** pass today. They pin what the code does with a predicted model so that supporting a second prediction
  source cannot loosen the guards silently.
* **Specification tests** are `xfail(strict=True)`. They state what DD-001 requires and fail today because the code does not do it yet.
  `strict=True` means the day the behaviour is implemented the test *XPASSes and the suite fails*, forcing the marker to be removed
  deliberately rather than left to rot. They contain no invented API: each uses only functions that exist.

Not written yet, because they need code that does not exist and inventing its interface here would only guess it: AlphaFold DB model
takes precedence over a prediction when both exist; a `source` tag on every structure record; a pLDDT gate threshold calibrated per
source from the 110-sequence ESMFold/AlphaFold comparison; the geometry descriptor over predicted structures.
"""
import pytest

from lantern.alphafold import (GATE_MINIMUM_PLDDT, NOT_SCORED, SCORABLE, NotAPredictedModel,
                               confidence_gate, residue_plddt, withhold_if_unconfident)

# The first lines of a real ESMFold (facebook/esmfold_v1) PDB: a PARENT record, then ATOM records with pLDDT (0-100) in the
# B-factor column. There is no ALPHAFOLD marker anywhere in the file.
ESMFOLD_PDB = """PARENT N/A
ATOM      1  N   MET A   1      24.054 -44.991 -21.473  1.00 52.44           N  
ATOM      2  CA  MET A   1      23.630 -44.710 -20.104  1.00 52.44           C  
ATOM      3  C   MET A   1      22.470 -43.790 -20.207  1.00 52.44           C  
ATOM      4  O   MET A   1      21.950 -43.560 -21.294  1.00 52.44           O  
ATOM      5  N   LYS A   2      22.060 -43.220 -19.067  1.00 63.37           N  
ATOM      6  CA  LYS A   2      20.960 -42.290 -19.012  1.00 63.37           C  
ATOM      7  C   LYS A   2      19.670 -43.020 -18.740  1.00 63.37           C  
ATOM      8  O   LYS A   2      19.620 -44.090 -18.150  1.00 63.37           O  
ATOM      9  N   ASP A   3      18.580 -42.440 -19.220  1.00 91.10           N  
ATOM     10  CA  ASP A   3      17.280 -43.060 -19.090  1.00 91.10           C  
ATOM     11  C   ASP A   3      16.270 -42.050 -18.610  1.00 91.10           C  
ATOM     12  O   ASP A   3      16.500 -40.870 -18.800  1.00 91.10           O  
TER
END
"""


@pytest.fixture
def esmfold_file(tmp_path):
    path = tmp_path / "ESMFOLD_TEST.pdb"
    path.write_text(ESMFOLD_PDB)
    return path


class TestCurrentBehaviour:
    def test_the_default_gate_threshold_is_alphafolds_and_is_overridable(self):
        """Another source's confidence is not on AlphaFold's scale (on 12 test sequences ESMFold loop pLDDT was 89-93 throughout),
        so a caller using a second source must be able to pass its own minimum rather than inherit this one."""
        assert GATE_MINIMUM_PLDDT == 70.0
        values = [60.0, 65.0, 66.0]
        assert confidence_gate(values)["verdict"] == NOT_SCORED
        assert confidence_gate(values, minimum=60.0)["verdict"] == SCORABLE

    def test_the_worst_residue_decides_not_the_mean(self):
        gate = confidence_gate([95.0, 95.0, 95.0, 95.0, 40.0])
        assert gate["verdict"] == NOT_SCORED
        assert gate["mean_plddt"] > GATE_MINIMUM_PLDDT      # the mean would have passed it

    def test_an_empty_region_is_not_scored_not_a_pass(self):
        assert confidence_gate([])["verdict"] == NOT_SCORED

    def test_a_withheld_score_is_none_never_zero(self):
        gate = confidence_gate([95.0, 40.0])
        withheld = withhold_if_unconfident(gate, {"score": 0.9, "call": "lanthanide-like"})
        assert withheld["score"] is None
        assert withheld["call"] == NOT_SCORED

    def test_a_file_without_a_prediction_marker_is_refused(self, esmfold_file):
        """Guards the B-factor trap: in an experimental file the same column is a temperature factor, so the parser
        must not read it as confidence on the strength of its position alone."""
        with pytest.raises(NotAPredictedModel):
            residue_plddt(esmfold_file)


class TestSpecificationDD001:
    @pytest.mark.xfail(strict=True, raises=NotAPredictedModel,
                       reason="DD-001: ESMFold output (PARENT N/A header, pLDDT 0-100 in the B-factor column) is refused today "
                              "because only AlphaFold markers are recognised.")
    def test_an_esmfold_pdb_yields_per_residue_plddt_on_a_zero_to_hundred_scale(self, esmfold_file):
        scores = residue_plddt(esmfold_file)
        assert set(scores) == {1, 2, 3}
        assert scores[1] == pytest.approx(52.44) and scores[3] == pytest.approx(91.10)
        assert all(0.0 <= v <= 100.0 for v in scores.values())
