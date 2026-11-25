"""Run many documents at once (done: you do not change this file for a ticket).

A batch is a list of jobs; each job is one model call. The runner keeps `concurrency` calls in flight. When the
provider answers "too many requests" (429), the job waits and tries again: about 1 s, 2 s, 4 s, 8 s, then 16 s
(each wait is varied a little, so refused jobs do not all come back together). After
`max_retries` refusals the job fails, and the document is listed so it can be run again.

With the scripted model nothing is really sent, so the runner simulates the clock instead: each call takes the
time the scripted model reports, and the provider accepts at most PROVIDER_LIMIT calls at once, like a real
account's rate limit. The numbers are then "simulated time", and the screen says so.
"""

import heapq
import os
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from app.llm import RateLimited

PROVIDER_LIMIT = 8  # scripted: calls the provider accepts at once (a real limit depends on your account)
REFUSAL_MS = 200  # scripted: how long a 429 takes to come back
BACKOFF_MS = [1000, 2000, 4000, 8000, 16000]
# Real runs never send more calls at once than this (set FDE_MAX_CONCURRENCY to match your account's limit).
# The scripted run is not capped, so the lesson can still show what 16 at once does.
MAX_LIVE_CONCURRENCY = int(os.environ.get("FDE_MAX_CONCURRENCY", PROVIDER_LIMIT))


def jitter(ms: int, i: int, attempt: int) -> int:
    """Wait a little longer or shorter than the backoff, so refused jobs do not all come back at the same moment."""
    return round(ms * (0.5 + ((i * 7919 + attempt * 104729) % 1000) / 1000))


def _sleep(seconds: float) -> None:
    time.sleep(seconds)


@dataclass
class Job:
    key: str  # "<doc_id>/<prompt>"
    run: callable  # does the call and returns the result (cached results return at once)
    latency_ms: int = 0  # scripted: how long the call takes


@dataclass
class BatchResult:
    done: dict = field(default_factory=dict)  # key -> result
    failed: list = field(default_factory=list)  # keys that ran out of retries
    refusals: int = 0  # 429s received
    wall_ms: int = 0
    simulated: bool = True
    latencies: list = field(default_factory=list)


def simulate(jobs: list[Job], concurrency: int, max_retries: int = 5, limit: int = PROVIDER_LIMIT) -> BatchResult:
    """The scripted run: an event clock, no sleeping. The results come from job.run() (scripted replies)."""
    res = BatchResult(simulated=True)
    queue =[(0, i, 0) for i in range(len(jobs))]  # (ready_at_ms, job index, attempts so far)
    heapq.heapify(queue)
    in_flight: list[tuple[int, int, bool]] = []  # (ends_at_ms, job index, accepted)
    now = 0
    while queue or in_flight:
        while queue and len(in_flight) < concurrency and queue[0][0] <= now:
            _, i, attempt = heapq.heappop(queue)
            accepted = sum(1 for _, _, a in in_flight if a) < limit
            end = now + (jobs[i].latency_ms if accepted else REFUSAL_MS)
            in_flight.append((end, i, accepted))
            jobs[i].attempt = attempt
        if not in_flight:
            now = queue[0][0]
            continue
        in_flight.sort()
        end, i, accepted = in_flight.pop(0)
        now = max(now, end)
        if accepted:
            res.done[jobs[i].key] = jobs[i].run()
            res.latencies.append(jobs[i].latency_ms)
        else:
            res.refusals += 1
            attempt = jobs[i].attempt + 1
            if attempt > max_retries:
                res.failed.append(jobs[i].key)
            else:
                heapq.heappush(queue, (now + jitter(BACKOFF_MS[min(attempt - 1, len(BACKOFF_MS) - 1)], i, attempt), i, attempt))
    res.wall_ms = now
    return res


def run_live(jobs: list[Job], concurrency: int, max_retries: int = 5) -> BatchResult:
    """The real run: threads, real calls, real waiting when the provider says 429."""
    res = BatchResult(simulated=False)
    started = time.perf_counter()

    def one(job: Job):
        for attempt in range(max_retries + 1):
            t = time.perf_counter()
            try:
                out = job.run()
                return job.key, out, round((time.perf_counter() - t) * 1000), attempt
            except RateLimited as e:
                res.refusals += 1
                if attempt == max_retries:
                    return job.key, None, 0, attempt
                wait = jitter(BACKOFF_MS[min(attempt, len(BACKOFF_MS) - 1)], hash(job.key) % 1000, attempt) / 1000
                _sleep(max(wait, getattr(e, "retry_after", 0.0)))  # wait for the provider if it said how long
        return job.key, None, 0, max_retries

    with ThreadPoolExecutor(max_workers=max(1, min(concurrency, MAX_LIVE_CONCURRENCY))) as pool:
        for key, out, ms, _ in pool.map(one, jobs):
            if out is None:
                res.failed.append(key)
            else:
                res.done[key] = out
                res.latencies.append(out.get("usage", {}).get("latency_ms") or ms)
    res.wall_ms = round((time.perf_counter() - started) * 1000)
    return res
