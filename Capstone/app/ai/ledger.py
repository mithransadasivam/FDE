"""Records every model call: the prompt (for the compliance scan), tokens, cost and latency (for the cost report)."""
from app.ai import router
from app.db import OpsSession
from app.models_ext import ModelCall


def record_call(agent: str, task: str, tier: str, model: str, system: str, user: str, output: str, latency_ms: float,
                simulated: bool, cached: bool = False, candidate_id: int | None = None, cost: float | None = None) -> None:
    """cost is the provider's own figure (LiteLLM's completion_cost) when there is one; otherwise the list price of the estimated tokens."""
    tin, tout = router.estimate_tokens(system + user), router.estimate_tokens(output)
    try:
        with OpsSession() as db:
            db.add(ModelCall(agent=agent, task=task, tier=tier, model=model, candidate_id=candidate_id, prompt_system=system,
                             prompt_user=user, tokens_in=tin, tokens_out=tout,
                             cost_usd=0.0 if cached else (cost if cost is not None else router.cost_usd(tier, tin, tout)), latency_ms=latency_ms,
                             simulated=simulated, cached=cached, sees_identity=(task == "identity")))
            db.commit()
    except Exception:  # the ledger must never break a request
        pass


def record_timed(agent: str, task: str, seconds: float, candidate_id: int | None = None, model: str = "local") -> None:
    """A transcription or text-to-speech call: it runs on this machine, so it costs nothing, but it is timed like every other call."""
    try:
        with OpsSession() as db:
            db.add(ModelCall(agent=agent, task=task, tier="local", model=model, candidate_id=candidate_id, prompt_system="", prompt_user="", tokens_in=0, tokens_out=0,
                             cost_usd=0.0, latency_ms=seconds * 1000, simulated=False, cached=False, sees_identity=False))
            db.commit()
    except Exception:
        pass
