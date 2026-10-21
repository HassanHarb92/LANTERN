"""Build Figure 2 and Figure 1 into a tmp dir; check the SVG/PNG files exist and are non-trivial."""
import pathlib, subprocess, sys
import pytest

pytest.importorskip("matplotlib")
pytest.importorskip("pandas")
REPO = pathlib.Path(__file__).resolve().parents[1]
SCRIPTS = REPO / "scripts/figures"


def _build(script, out):
    r = subprocess.run([sys.executable, str(SCRIPTS / script), "--out", str(out)], capture_output=True, text=True, cwd=REPO)
    assert r.returncode == 0, r.stderr[-2000:]


def _check(files):
    for f in files:
        assert f.exists(), f
        assert f.stat().st_size > (2000 if f.suffix == ".svg" else 5000), f


def test_figure2(tmp_path):
    _build("build_figure2.py", tmp_path)
    names = ["ranking", "composition", "cn_distribution", "paired_sites", "retrieval", "alphafold"]
    _check([tmp_path / f"Figure2.{e}" for e in ("svg", "png")]
           + [tmp_path / "panels" / f"Fig2{l}_{n}.{e}" for l, n in zip("ABCDEF", names) for e in ("svg", "png")])


def test_figure1(tmp_path):
    _build("build_figure1.py", tmp_path)
    names = ["flow", "harness", "caricature", "ui_shortlist", "ui_explorer"]
    _check([tmp_path / f"Figure1.{e}" for e in ("svg", "png")]
           + [tmp_path / "panels" / f"Fig1{l}_{n}.{e}" for l, n in zip("ABCDE", names) for e in ("svg", "png")])
