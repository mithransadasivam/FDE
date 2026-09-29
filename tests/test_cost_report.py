from scripts.cost_report import format_report, load_usage, output_share, summarise

CSV = """timestamp,model,prompt_tokens,completion_tokens,seconds,cost
t1,cheap,1000000,0,1.0,1.0
t2,cheap,0,1000000,1.0,5.0
t3,strong,100000,100000,2.0,1.8
"""
PRICES = {"cheap": (1.0, 5.0), "strong": (3.0, 15.0)}


def make(tmp_path):
    p = tmp_path / "usage.csv"
    p.write_text(CSV, encoding="utf-8")
    return summarise(load_usage(p), PRICES)


def test_per_model_totals(tmp_path):
    s = make(tmp_path)
    assert s["cheap"]["calls"] == 2
    assert (s["cheap"]["in_tok"], s["cheap"]["out_tok"]) == (1_000_000, 1_000_000)
    assert s["cheap"]["cost"] == 6.0 and s["cheap"]["per_call"] == 3.0
    assert round(s["strong"]["cost"], 6) == 1.8


def test_output_share_and_projection(tmp_path):
    s = make(tmp_path)
    # output cost: cheap 5.0 + strong 100k*15/1M = 1.5 -> 6.5 of 7.8
    assert round(output_share(s), 4) == round(6.5 / 7.8, 4)
    assert s["cheap"]["monthly"] == 3.0 * 1000 * 30
    assert "output tokens are 83% of total cost" in format_report(s)
