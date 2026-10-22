"""Day 16, Activity 3: measure_stream() times the first word and the whole answer."""

from app.perf import measure_stream


class Clock:
    """A clock that moves on by a fixed step every time it is read."""

    def __init__(self, step):
        self.t, self.step = 0.0, step

    def __call__(self):
        self.t += self.step
        return self.t


def slow(pieces, clock, wait):
    for p in pieces:
        clock.t += wait
        yield p


def test_text_is_every_piece_joined():
    m = measure_stream(
        iter(["A VPN ", "session ", "lasts 12 hours."]), 0.0, clock=Clock(0.1)
    )
    assert m["text"] == "A VPN session lasts 12 hours."


def test_first_token_and_total_times():
    clock = Clock(0.0)
    m = measure_stream(
        slow(["first", " second", " third"], clock, 0.5), 0.0, clock=clock
    )
    assert m["first_token_seconds"] == 0.5 and m["seconds"] == 1.5


def test_empty_pieces_do_not_count_as_the_first_token():
    clock = Clock(0.0)
    m = measure_stream(slow(["", "", "hello"], clock, 1.0), 0.0, clock=clock)
    assert m["first_token_seconds"] == 3.0


def test_no_text_at_all_means_no_first_token():
    m = measure_stream(iter(["", ""]), 0.0, clock=Clock(0.2))
    assert m == {"text": "", "first_token_seconds": None, "seconds": 0.2}


def test_times_are_measured_from_start_and_rounded():
    clock = Clock(0.0)
    clock.t = 10.0
    m = measure_stream(slow(["a"], clock, 0.12345), 10.0, clock=clock)
    assert m["first_token_seconds"] == 0.123 and m["seconds"] == 0.123
