"""Which browser tests the runner leaves out: the fast ones by default, and exactly what was asked for added back."""
import pytest

from scripts.browser_tests import marker_expression


@pytest.mark.parametrize("real,slow,no_index,expected", [
    (False, False, False, "not slow and not real"),            # the default: fake only
    (True, False, False, "not slow"),                           # --real
    (False, True, False, ""),                                   # --slow implies --real: everything
    (True, True, False, ""),
    (False, False, True, "not slow and not real and not index"),  # the CI fast job
    (True, False, True, "not slow and not index"),
])
def test_marker_expression(real, slow, no_index, expected):
    assert marker_expression(real, slow, no_index) == expected
