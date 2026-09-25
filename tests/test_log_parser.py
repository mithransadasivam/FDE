from pathlib import Path

from tools.log_parser import count_levels

SAMPLE_LOG = Path(__file__).resolve().parent.parent / "data" / "sample.log"


def test_count_levels_on_sample_log():
    with open(SAMPLE_LOG) as f:
        counts = count_levels(f)
    assert counts == {"INFO": 1, "WARNING": 1, "ERROR": 2}
