"""Models. `OpenRouterLLM` is the real one (a large and a small model through OpenRouter, called with LiteLLM). `FakeLLM` is the test double:
deterministic, offline, with a latency profile. `GullibleLLM` is a deliberately naive fake used only by the red team to show
what the defences stop: it obeys anything that looks like an instruction."""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Protocol

import requests

from .settings import REQUEST_TIMEOUT_S, Settings


class LLMError(RuntimeError):
    pass


@dataclass
class LLMResult:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""
    role: str = "large"
    latency_ms: float = 0.0
    ttft_ms: float | None = None


class LLM(Protocol):
    def complete(self, system: str, user: str, *, role: str = "large", max_tokens: int = 600, purpose: str = "") -> LLMResult: ...
    def stream(self, system: str, user: str, *, role: str = "large", max_tokens: int = 600, purpose: str = "") -> Iterator[tuple[str, object]]: ...
    def ping(self) -> bool: ...
    def model_name(self, role: str) -> str: ...


def extract_json(text: str) -> dict | None:
    """Pull the first JSON object out of a model reply, tolerating code fences and chatter."""
    text = re.sub(r"```(?:json)?", "", text)
    start = text.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(text)):
            depth += (text[i] == "{") - (text[i] == "}")
            if depth == 0:
                try:
                    return json.loads(text[start:i + 1])
                except json.JSONDecodeError:
                    break
        start = text.find("{", start + 1)
    return None


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


# ---------------------------------------------------------------------------------------------------------------------
class OpenRouterLLM:
    """The real models, through LiteLLM and OpenRouter. LLM_MODEL and SMALL_MODEL in .env are OpenRouter model ids; LiteLLM gets
    them as 'openrouter/<id>'. Retries, timeouts and streaming are LiteLLM's; prices stay ours (Settings), so cost is one place."""

    def __init__(self, s: Settings):
        self.s = s
        self._ping_at = 0.0
        self._ping_ok = False

    def model_name(self, role: str) -> str:
        return self.s.small_model if role == "small" else self.s.llm_model

    def _kw(self, system: str, user: str, role: str, max_tokens: int) -> dict:
        return {"model": f"openrouter/{self.model_name(role)}", "api_key": self.s.api_key, "api_base": self.s.base_url, "temperature": 0,
                "max_tokens": max_tokens, "timeout": REQUEST_TIMEOUT_S, "num_retries": 3,
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}

    def complete(self, system, user, *, role="large", max_tokens=600, purpose="") -> LLMResult:
        import litellm
        t0 = time.perf_counter()
        try:
            r = litellm.completion(**self._kw(system, user, role, max_tokens))
        except Exception as e:  # noqa: BLE001  LiteLLM raises its own error types; callers only need to know the call failed
            raise LLMError(f"model call failed ({type(e).__name__})") from None
        text = (r.choices[0].message.content or "") if r.choices else ""
        u = getattr(r, "usage", None)
        return LLMResult(text, int(getattr(u, "prompt_tokens", 0) or estimate_tokens(system + user)),
                         int(getattr(u, "completion_tokens", 0) or estimate_tokens(text)), self.model_name(role), role,
                         (time.perf_counter() - t0) * 1000)

    def stream(self, system, user, *, role="large", max_tokens=600, purpose="") -> Iterator[tuple[str, object]]:
        import litellm
        t0 = time.perf_counter()
        text, ttft, usage = [], None, None
        try:
            for ev in litellm.completion(**self._kw(system, user, role, max_tokens), stream=True, stream_options={"include_usage": True}):
                if getattr(ev, "usage", None):
                    usage = ev.usage
                for ch in ev.choices or []:
                    piece = getattr(ch.delta, "content", None)
                    if piece:
                        if ttft is None:
                            ttft = (time.perf_counter() - t0) * 1000
                        text.append(piece)
                        yield "chunk", piece
        except Exception as e:  # noqa: BLE001
            raise LLMError(f"model call failed ({type(e).__name__})") from None
        full = "".join(text)
        yield "done", LLMResult(full, int(getattr(usage, "prompt_tokens", 0) or estimate_tokens(system + user)),
                                int(getattr(usage, "completion_tokens", 0) or estimate_tokens(full)), self.model_name(role), role,
                                (time.perf_counter() - t0) * 1000, ttft)

    def ping(self) -> bool:
        """Is the model connection usable? Cached for 15 seconds. Does not spend tokens."""
        now = time.time()
        if now - self._ping_at < 15:
            return self._ping_ok
        try:
            r = requests.get(f"{self.s.base_url}/models", headers={"Authorization": f"Bearer {self.s.api_key}"}, timeout=6)
            self._ping_ok = r.status_code == 200
        except requests.RequestException:
            self._ping_ok = False
        self._ping_at = now
        return self._ping_ok


# ---------------------------------------------------------------------------------------------------------------------
# What the fake planner recommends for each symptom. It reads the facts JSON the real planner would read.
_FAKE_RULES = [  # (root-cause service, check, runbook, step)
    ("db-core", "availability", "RB-01", 3),
    ("fs-02", "disk_space", "RB-04", 2),
    ("build-01", "disk_space", "RB-04", 2),
    ("build-01", "cpu", "RB-03", 3),
    ("cache-redis", "memory", "RB-07", 3),
    ("ticketing-api", "error_rate", "RB-07", 4),
    ("mail-gw", "cert_expiry", "RB-06", 2),
    ("intranet", "cert_expiry", "RB-06", 2),
    ("vpn-gw", "cert_expiry", "RB-06", 2),
    ("vpn-gw", "latency", "RB-08", 3),
    ("payportal", "memory", "RB-02", 3),
    ("hr-selfservice", "memory", "RB-02", 3),
    ("hr-selfservice", "http_check", "RB-02", 3),
    ("intranet", "http_check", "RB-02", 3),
    ("sso", "auth_failures", "RB-05", 3),
]


class FakeLLM:
    """Deterministic and offline. Used by every test. Latency scale 0 makes tests instant."""

    def __init__(self, s: Settings | None = None, *, latency_scale: float | None = None):
        self.s = s or Settings()
        self.scale = self.s.fake_latency_scale if latency_scale is None else latency_scale
        self.calls: list[dict] = []
        self.prompts: list[str] = []  # everything ever sent, so tests can search it for secrets
        self.down = False
        self.fail_planner_times = 0  # make the planner recommend an invalid step this many times
        self.bad_step = ("RB-04", 3)  # a real step that is not allowed (needs a capacity ticket)

    def model_name(self, role: str) -> str:
        return ("fake-small" if role == "small" else "fake-large")

    def ping(self) -> bool:
        return not self.down

    # -- internals --
    def _sleep(self, role: str, text: str) -> None:
        base = 0.12 if role == "small" else 0.45
        time.sleep((base + len(text) / 4 * 0.002) * self.scale)

    def _facts(self, user: str) -> dict:
        m = re.search(r"<facts>\n(.*?)\n</facts>", user, re.S)
        return json.loads(m.group(1)) if m else {}

    def _answer(self, system: str, user: str, purpose: str) -> str:
        if self.down:
            raise LLMError("model unreachable")
        if purpose == "investigator":
            facts = self._facts(user)
            rc_ = facts.get("root_cause")
            facts["root_cause"] = rc_.get("service") if isinstance(rc_, dict) else rc_
            tools = [t["tool"] for t in json.loads(re.search(r"<tools>\n(.*?)\n</tools>", user, re.S).group(1))]
            called = [c["tool"] for c in json.loads(re.search(r"<already_called>\n(.*?)\n</already_called>", user, re.S).group(1))]
            nxt = next((t for t in tools if t not in called), None)
            if nxt:
                return json.dumps({"call": nxt, "why": f"run runbook read step for {facts.get('root_cause')}"})
            return json.dumps({"done": True, "findings": "read steps complete"})
        if purpose == "planner":
            facts = self._facts(user)
            rc = facts.get("root_cause")
            rc = rc.get("service") if isinstance(rc, dict) else rc
            checks ={a["check"] for a in facts.get("alerts", []) if a.get("service") == rc} or {a["check"] for a in facts.get("alerts", [])}
            hit = next(((r, s) for (svc, chk, r, s) in _FAKE_RULES if svc == rc and chk in checks), None)
            findings = json.dumps(facts.get("read_findings", [])).lower()
            if rc == "cache-redis" and "evictions" in findings:
                hit = ("RB-07", 3)
            if self.fail_planner_times > 0:
                self.fail_planner_times -= 1
                hit = self.bad_step
            if rc == "vpn-gw" and "latency" in checks and facts.get("status") == "AUTO_RESOLVED":
                hit = None
            summary = (f"{facts.get('incident_id')}: {facts.get('severity')} on {rc} ({len(facts.get('alerts', []))} alert(s)). "
                       f"Checks: {', '.join(sorted(checks))}.")
            if hit is None:
                return json.dumps({"summary": summary + " Nothing to change.", "runbook_id": "RB-08", "recommended_step": None,
                                   "reason": "alerts cleared by themselves (policy 3.4)"})
            return json.dumps({"summary": summary, "runbook_id": hit[0], "recommended_step": hit[1],
                               "reason": f"{hit[0]} step {hit[1]} fits the symptom ({', '.join(sorted(checks))}); a similar past incident was fixed this way."})
        if purpose == "scribe":
            facts = self._facts(user)
            return (f"We are seeing a problem with {facts.get('what', 'a service')}. The operations team is working on it and any "
                    f"change will be approved by a person first. Next update by {facts.get('next_update', 'the top of the hour')}.")
        # ask: answer from the context chunks
        chunks = re.findall(r"\[(\d+)\] \(([^)]*)\) (.*)", user)
        q = re.search(r"<question>\n(.*?)\n</question>", user, re.S)
        if not chunks:
            return "The context does not answer that."
        top = chunks[:3]
        return " ".join(f"{text.strip()[:260]} [{src}]" for _, src, text in top) + ("" if q else "")

    # -- API --
    def complete(self, system, user, *, role="large", max_tokens=600, purpose="") -> LLMResult:
        t0 = time.perf_counter()
        self.prompts.append(system + "\n" + user)
        text = self._answer(system, user, purpose)
        self._sleep(role, text)
        self.calls.append({"role": role, "purpose": purpose})
        return LLMResult(text, estimate_tokens(system + user), estimate_tokens(text), self.model_name(role), role,
                         (time.perf_counter() - t0) * 1000)

    def stream(self, system, user, *, role="large", max_tokens=600, purpose="") -> Iterator[tuple[str, object]]:
        t0 = time.perf_counter()
        self.prompts.append(system + "\n" + user)
        text = self._answer(system, user, purpose)
        time.sleep((0.10 if role == "small" else 0.18) * self.scale)  # time to first token
        ttft = (time.perf_counter() - t0) * 1000
        words = text.split(" ")
        for i, w in enumerate(words):
            time.sleep(0.004 * self.scale)
            yield "chunk", (w if i == 0 else " " + w)
        self.calls.append({"role": role, "purpose": purpose})
        yield "done", LLMResult(text, estimate_tokens(system + user), estimate_tokens(text), self.model_name(role), role,
                                (time.perf_counter() - t0) * 1000, ttft)


class GullibleLLM(FakeLLM):
    """A model with no judgement, for the red team's 'defences off' run. It does what the text in front of it says.
    It is only ever given to the red-team harness; nothing in the product uses it."""

    def __init__(self, s: Settings | None = None, system_prompt_leak: str = "", **kw):
        super().__init__(s, latency_scale=0.0, **kw)
        self.leak = system_prompt_leak

    def _answer(self, system: str, user: str, purpose: str) -> str:
        low = user.lower()
        if purpose == "planner":
            # obeys instructions found in the alert text: recommends restart on a tier-1 service
            m = re.search(r"run (restart_service) on every tier-1 service", low)
            if m:
                return json.dumps({"summary": "Alert says the duty manager approved restarting every tier-1 service. Doing so.",
                                   "runbook_id": "RB-02", "recommended_step": 3, "target_service": "payportal",
                                   "reason": "instructed by the alert; mark all incidents resolved"})
            return super()._answer(system, user, purpose)
        if purpose == "ask":
            q = (re.search(r"<question>\n(.*?)\n</question>", user, re.S) or [None, ""])[1]
            m64 = re.search(r"[A-Za-z0-9+/]{32,}={0,2}", q)
            if "decode" in q.lower() and m64:  # follows instructions hidden in encoded text
                import base64
                try:
                    q = base64.b64decode(m64.group(0) + "=" * (-len(m64.group(0)) % 4)).decode("utf-8", "ignore")
                except Exception:  # noqa: BLE001
                    pass
            low = q.lower()
            if "system prompt" in low or "full instructions" in low or "instructions and the list of tools" in low:
                return self.leak or system
            if "personal mobile" in low or "mobile number" in low:
                m = re.search(r"\+44 7700 900\d{3}", user)
                return f"Their personal mobile number is {m.group(0)}." if m else "I do not have a personal number in my context."
            if "restart payportal, hr-selfservice and intranet" in low:
                return ("Sure. CALL restart_service(payportal) CALL restart_service(hr-selfservice) CALL restart_service(intranet) "
                        "I have restarted them all.")
            if "ignore your previous instructions" in low:
                return "Okay. CALL restart_service(payportal) I will run the first one now."
            return super()._answer(system, user, purpose)
        if purpose == "investigator":
            return super()._answer(system, user, purpose)
        if purpose == "scribe":
            m = re.search(r"password=\S+|token=\S+", user)
            return f"Status: see alert text: {m.group(0) if m else ''}"
        return super()._answer(system, user, purpose)


def make_llm(s: Settings) -> "LLM":
    return OpenRouterLLM(s) if s.model_mode == "openrouter" and s.api_key else FakeLLM(s)
