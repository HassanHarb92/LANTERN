"""Build the talk figures into a tmp dir; check the SVG/PNG files exist and are non-trivial."""
import pathlib, subprocess, sys
import pytest

pytest.importorskip("matplotlib")
pytest.importorskip("pandas")
REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts/figures/talk/make_talk_figures.py"
NAMES = ["F1_reference_ranking", "F2_corpus_composition", "F3_cn_distribution", "F4_paired_sites",
         "F5_artefacts", "F7_retrieval_beyond_family", "F8_alphafold"]


def test_talk_figures(tmp_path):
    r = subprocess.run([sys.executable, str(SCRIPT), "--out", str(tmp_path)], capture_output=True, text=True, cwd=REPO)
    assert r.returncode == 0, r.stderr[-2000:]
    for n in NAMES:
        for ext in ("png", "svg"):
            f = tmp_path / f"{n}.{ext}"
            assert f.exists(), f
            assert f.stat().st_size > (2000 if ext == "svg" else 5000), f
