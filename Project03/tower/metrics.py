"""Counters and timings behind /metrics: requests, errors, model calls, tokens, cost, p50/p95, cache, routes, time to first token."""
from __future__ import annotations

import threading
from collections import Counter, defaultdict, deque

from .settings import Settings


def percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    k = (len(v) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)


class Metrics:
    def __init__(self, s: Settings):
        self.s = s
        self._lock = threading.Lock()
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self.requests = Counter()
            self.errors = Counter()
            self.latency: dict[str, deque] = defaultdict(lambda: deque(maxlen=5000))
            self.model_calls = Counter()  # by purpose
            self.model_cost = defaultdict(float)  # by purpose
            self.tokens_in = 0
            self.tokens_out = 0
            self.routes = Counter()  # data / small / large / cache / blocked
            self.route_latency: dict[str, deque] = defaultdict(lambda: deque(maxlen=2000))
            self.cache = Counter()
            self.ttft: deque = deque(maxlen=2000)
            self.ttfs: deque = deque(maxlen=2000)  # first visible sentence (after the output check)
            self.ask_total = 0
            self.briefs = 0
            self.blocked = Counter()  # by guardrail

    # -- price of a call from its tokens (US dollars per million tokens) --
    def price(self, role: str, tin: int, tout: int) -> float:
        pin, pout = ((self.s.small_in_price, self.s.small_out_price) if role == "small"
                     else (self.s.llm_in_price, self.s.llm_out_price))
        return (tin * pin + tout * pout) / 1_000_000

    def request(self, endpoint: str, ms: float, error: bool) -> None:
        with self._lock:
            self.requests[endpoint] += 1
            self.latency[endpoint].append(ms)
            if error:
                self.errors[endpoint] += 1

    def model_call(self, purpose: str, role: str, tin: int, tout: int) -> float:
        cost = self.price(role, tin, tout)
        with self._lock:
            self.model_calls[purpose] += 1
            self.model_cost[purpose] += cost
            self.tokens_in += tin
            self.tokens_out += tout
        return cost

    def route(self, route: str, ms: float, ttft: float | None = None, ttfs: float | None = None) -> None:
        with self._lock:
            self.routes[route] += 1
            self.ask_total += 1
            self.route_latency[route].append(ms)
            if ttft is not None:
                self.ttft.append(ttft)
            if ttfs is not None:
                self.ttfs.append(ttfs)

    def cache_event(self, hit: bool) -> None:
        with self._lock:
            self.cache["hit" if hit else "miss"] += 1

    def brief_done(self) -> None:
        with self._lock:
            self.briefs += 1

    def block(self, why: str) -> None:
        with self._lock:
            self.blocked[why] += 1

    def snapshot(self) -> dict:
        with self._lock:
            all_ms = [x for q in self.latency.values() for x in q]
            ask_ms = [x for q in self.route_latency.values() for x in q]  # whole-answer time, streaming included
            brief_cost = sum(self.model_cost[p] for p in ("investigator", "planner", "scribe"))
            ask_cost = self.model_cost["ask"]
            hits, misses = self.cache["hit"], self.cache["miss"]
            return {
                "requests": dict(self.requests),
                "requests_total": sum(self.requests.values()),
                "errors": dict(self.errors),
                "errors_total": sum(self.errors.values()),
                "model_calls": dict(self.model_calls),
                "model_calls_total": sum(self.model_calls.values()),
                "tokens_in": self.tokens_in,
                "tokens_out": self.tokens_out,
                "tokens_total": self.tokens_in + self.tokens_out,
                "cost_usd_total": round(sum(self.model_cost.values()), 6),
                "cost_by_purpose": {k: round(v, 6) for k, v in self.model_cost.items()},
                "latency_ms": {"p50": round(percentile(all_ms, 50), 2), "p95": round(percentile(all_ms, 95), 2)},
                "ask_latency_ms": {"p50": round(percentile(ask_ms, 50), 2), "p95": round(percentile(ask_ms, 95), 2), "n": len(ask_ms)},
                "cost_per_incident_brief_usd": round(brief_cost / self.briefs, 6) if self.briefs else 0.0,
                "cost_per_1000_questions_usd": round(ask_cost / self.ask_total * 1000, 4) if self.ask_total else 0.0,
                "briefs": self.briefs,
                "questions": self.ask_total,
                "routes": dict(self.routes),
                "route_p50_ms": {r: round(percentile(list(q), 50), 2) for r, q in self.route_latency.items()},
                "cache": {"hits": hits, "misses": misses, "hit_rate": round(hits / (hits + misses), 3) if hits + misses else 0.0},
                "ttft_ms": {"p50": round(percentile(list(self.ttft), 50), 2), "p95": round(percentile(list(self.ttft), 95), 2)},
                "first_visible_ms": {"p50": round(percentile(list(self.ttfs), 50), 2)},
                "blocked": dict(self.blocked),
            }

    def prometheus(self) -> str:
        s = self.snapshot()
        lines = [f"tower_requests_total {s['requests_total']}", f"tower_errors_total {s['errors_total']}",
                 f"tower_model_calls_total {s['model_calls_total']}", f"tower_tokens_total {s['tokens_total']}",
                 f"tower_cost_usd_total {s['cost_usd_total']}", f"tower_latency_p50_ms {s['latency_ms']['p50']}",
                 f"tower_latency_p95_ms {s['latency_ms']['p95']}", f"tower_cache_hit_rate {s['cache']['hit_rate']}"]
        return "\n".join(lines) + "\n"
