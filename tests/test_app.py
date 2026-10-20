"""The page itself, driven headlessly with no network and no language model.

The app is the product, so the parts of it that can be checked without a
gateway are checked here: that the canonical question renders a result, and
that the per-structure widgets belong to the structures they are drawn under.

Everything a model would add is out of scope -- `scripts/drive_app.py` drives
the narration against a live gateway, because that genuinely needs one.
"""
import pathlib

import pytest

from lantern.discover import NARRATION_MAX_TOKENS, NARRATION_TIMEOUT_S
from lantern.plan import SOURCE_FALLBACK

AppTest = pytest.importorskip("streamlit.testing.v1").AppTest

APP = str(pathlib.Path(__file__).resolve().parent.parent / "app.py")
CANONICAL = "what proteins should I try for capturing Ce3+"


# app.py calls load_dotenv(), so on a developer's machine these tests would
# otherwise reach the real gateway -- measured: parsed_by came back "llm".
# That makes the suite slow, credential-dependent, and a different test here
# than in CI. load_dotenv() does not override variables that are already set,
# and an empty one still counts as set, so emptying them is what keeps the
# page offline whether or not a .env exists.
CREDENTIALS = ("ARGO_USER", "ARGO_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY")


@pytest.fixture(scope="module")
def page():
    """The canonical question asked once through the real widgets."""
    with pytest.MonkeyPatch.context() as env:
        for variable in CREDENTIALS:
            env.setenv(variable, "")
        app = AppTest.from_file(APP, default_timeout=300).run()
        app.text_input(key="question").set_value(CANONICAL).run()
        app.button[0].click().run()
        assert not app.exception, [str(e.value) for e in app.exception]
        yield app


class TestTheQuestionBoxProducesAPage:

    def test_it_answers_without_a_gateway(self, page):
        record = page.session_state["record"]
        assert record["answered"] is True
        assert record["plan"]["target"] == "Ce3+"
        assert record["plan"]["parsed_by"] == SOURCE_FALLBACK, (
            "this test reached a live model; the offline guarantee it is "
            "supposed to be checking was not exercised")

    def test_it_draws_a_tab_per_verified_candidate(self, page):
        assert len(page.tabs) == len(page.session_state["record"]["evidence"])

    def test_it_draws_the_rules_table_and_a_site_table_per_structure(self, page):
        evidence = page.session_state["record"]["evidence"]
        assert len(page.dataframe) == 1 + len(evidence)

    def test_it_reports_no_errors(self, page):
        assert [e.value for e in page.error] == []


class TestEachStructuresWidgetsBelongToThatStructure:
    """A per-structure widget built in a loop must capture that iteration's
    data. `format_func=lambda i: views[i]` closes over the loop variable
    instead, so every structure's formatter reads the last structure's labels:
    the options render correctly, because Streamlit formats them inside the
    selectbox call, and every later call is wrong. It is also an IndexError
    whenever an earlier structure has more sites than the last one -- 8FNR has
    14 and 8FNS has 4, so the canonical question is already such a case."""

    def test_each_site_picker_formats_with_its_own_structures_labels(self, page):
        pickers = [box for box in page.selectbox if box.label == "View"]
        evidence = page.session_state["record"]["evidence"]
        assert len(pickers) == len(evidence)
        for box, ev in zip(pickers, evidence):
            elements = {s["deposited_element"].upper() for s in ev["sites"]}
            formatted = box.format_func(box.value)
            assert any(formatted.upper().startswith(e) for e in elements), (
                f"{ev['pdb_id']} holds {sorted(elements)} but its picker "
                f"formatted {formatted!r}")

    def test_every_option_of_every_picker_is_reachable(self, page):
        """The IndexError half: formatting the last index of the longest
        picker is what a stale closure cannot survive."""
        for box in [b for b in page.selectbox if b.label == "View"]:
            for index in range(len(box.options)):
                assert isinstance(box.format_func(index), str)

    def test_the_page_can_be_rerun(self, page):
        """A stale closure surfaces here too: Streamlit re-reads widget state
        on the next pass, and a formatter pointing at a shorter list throws
        before anything renders."""
        page.run()
        assert not page.exception, [str(e.value) for e in page.exception]


class TestTheNarrationBudgetIsWiredToThePage:
    """The cap and the timeout were measured together; the page has to use
    both or it reintroduces the truncation they were measured to fix."""

    def test_the_page_builds_its_narrator_with_the_measured_timeout(self):
        source = pathlib.Path(APP).read_text()
        assert "NARRATION_TIMEOUT_S" in source, (
            "the narration client must be built with the long timeout, not "
            "the shared one sized for question parsing")
        assert NARRATION_TIMEOUT_S > NARRATION_MAX_TOKENS / 100
