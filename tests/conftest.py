"""Suite-wide guards that have to hold before any test runs.

The run archive is committed to the repository, and the app writes to it
whenever a question is answered -- including when the question is answered
by a test driving the real page. Left alone, a passing suite would rewrite
fifteen tracked files and add its own fixtures to the archive, so `git
status` after `pytest` would never be clean and the archive would fill with
runs nobody asked for.

Redirecting the archive for the whole session fixes that at the root rather
than asking every test that touches the page to remember. Tests that are
specifically about the committed archive read `DEFAULT_RUNS_DIR` instead,
which this does not move.
"""
import pytest

from lantern.runs import RUNS_ENV


@pytest.fixture(scope="session", autouse=True)
def archive_outside_the_repository(tmp_path_factory):
    """Point the run archive at a temporary directory for the whole run."""
    with pytest.MonkeyPatch.context() as environment:
        environment.setenv(RUNS_ENV, str(tmp_path_factory.mktemp("runs")))
        yield
