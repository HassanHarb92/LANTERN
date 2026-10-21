"""The hand-label sheet is read back by a regex, which is the one place a typo is silent.

A sheet is a human-edited file, so the parser's job is to tell a filled slot from an
empty one and to refuse anything that is neither. Getting that wrong does not crash: it
scores the judge against labels nobody wrote.
"""
import pytest

from scripts.critic_label import read_labels

SHEET = """# Critic hand labels

Put one of `supports` / `contradicts` / `no_evidence` after `label:`.

---

## q1:c1  label: supports

CLAIM
  Dy3+ in lanmodulin EF-hand sites has coordination number 9

EVIDENCE -- 1 passage(s), exactly as the judge sees them
  [1] 10.0000/x | 2022 | crossref | BM25 9.9
      A title

      An abstract.

---

## q1:c2  label:

CLAIM
  Dy3+ in lanmodulin EF-hand sites has coordination number 7

---

## q2:c1  label: no_evidence

CLAIM
  Something else entirely

---
"""


def test_a_filled_slot_is_read_and_an_empty_one_is_skipped(tmp_path):
    p = tmp_path / "sheet.md"
    p.write_text(SHEET)
    assert read_labels(p) == {"q1:c1": "supports", "q2:c1": "no_evidence"}


def test_an_unfilled_slot_does_not_swallow_the_next_line(tmp_path):
    """`\\s*` after `label:` matches newlines, so an empty slot once read the next
    word in the file -- "CLAIM" -- as its label. An unlabelled claim must stay
    unlabelled rather than silently acquire a nonsense one."""
    p = tmp_path / "sheet.md"
    p.write_text(SHEET)
    assert "q1:c2" not in read_labels(p)


def test_a_misspelled_label_stops_the_run_and_names_the_typo(tmp_path):
    """Silently dropping it would score the judge on fewer claims than the sheet says."""
    p = tmp_path / "sheet.md"
    p.write_text(SHEET.replace("label: supports", "label: suports"))
    with pytest.raises(SystemExit) as exc:
        read_labels(p)
    assert "suports" in str(exc.value) and "q1:c1" in str(exc.value)


def test_an_entirely_blank_sheet_yields_nothing(tmp_path):
    p = tmp_path / "sheet.md"
    p.write_text(SHEET.replace("label: supports", "label:").replace("label: no_evidence", "label:"))
    assert read_labels(p) == {}
