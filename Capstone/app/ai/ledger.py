"""Records every model call: the prompt (for the compliance scan), tokens, cost and latency (for the cost report)."""
from app.ai import router
from app.db import OpsSession
from app.models_ext import ModelCall


def record_call(agent: str, task: str, tier: str, model: str, system: str, user: str, output: str, latency_ms: float,
                simulated: bool, cached: bool = False, candidate_id: int | None = None) -> None:
    tin, tout = router.estimate_tokens(system + user), router.estimate_tokens(output)
    try:
        with OpsSession() as db:
            db.add(ModelCall(agent=agent, task=task, tier=tier, model=model, candidate_id=candidate_id, prompt_system=system,
                             prompt_user=user, tokens_in=tin, tokens_out=tout,
                             cost_usd=0.0 if cached else router.cost_usd(tier, tin, tout), latency_ms=latency_ms,
                             simulated=simulated, cached=cached, sees_identity=(task == "identity")))
            db.commit()
    except Exception:  # the ledger must never break a request
        pass
