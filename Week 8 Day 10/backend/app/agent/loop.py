"""The operations agent's loop (done, not a ticket): think, check, act, observe, until the exception is worked.

Each turn the model replies with one tool call. Before the tool runs:
  - check_limits() may stop the run (ENG-902)
  - the screen action is matched to a real control on the screen (ENG-901)
  - gate() decides allow, ask or deny (ENG-903); "ask" waits for a person's approval of exactly that action
Then the tool runs as the person, the result goes back to the model, and the step is saved with a screenshot.

Day 10: when the approver leaves the approval pending, the run ends at the ask, with status "waiting_approval". The case
workflow keeps the proposal, waits durably for the person, and a separate step makes exactly the approved write.
"""

import json
import time
from pathlib import Path
from typing import Callable

from app.agent import actions, scripted
from app.agent.approvals import gate
from app.agent.limits import check_limits
from app.agent.models import AgentReply, Approval, Run, ScreenError, Step
from app.integration.models import ToolRefused
from app.llm import LLMError, _estimate_tokens, _json_text

HARD_CAP = 40  # a safety net for the course: no run goes past 40 steps, even before ENG-902


def system_prompt(prompt_text: str, playbook: str) -> str:
    return prompt_text.replace("{{TOOLS}}", actions.TOOLS_DOC).replace("{{PLAYBOOK}}", playbook)


def _model_turn(client, system: str, messages: list[dict], ctx: actions.RunContext, prompt_text: str, last_obs: str):
    if getattr(client, "is_fake", False):
        ctx.facts["chosen"] = ctx.facts.get("chosen", {})
        reply = scripted.next_action(ctx.run.ticket_id, ctx.facts, ctx.elements, ctx.title, last_obs, prompt_text)
        tin = _estimate_tokens(system + "".join(m["content"] for m in messages))
        return reply, tin, _estimate_tokens(reply.model_dump_json())
    msgs = list(messages)
    for _ in range(2):
        text = client.complete(system, msgs)
        u = client.calls[-1] if getattr(client, "calls", None) else {}
        try:
            return AgentReply.model_validate(json.loads(_json_text(text))), u.get("input_tokens", 0), u.get("output_tokens", 0)
        except ValueError as e:
            msgs += [{"role": "assistant", "content": text},
                     {"role": "user", "content": f"That reply was not valid ({str(e)[:200]}). Reply with one JSON object only."}]
    raise LLMError("The model did not reply with a tool call, even after a retry")


def run_agent(ctx: actions.RunContext, client, prompt_text: str, playbook: str, limits: dict, rules: list[dict],
              approver: Callable[[Approval], Approval], save: Callable[[Run], None], approvals: list[Approval] | None = None) -> Run:
    run = ctx.run
    run.started_at = run.started_at or time.time()
    system = system_prompt(prompt_text, playbook)
    messages = [{"role": "user", "content": f"Work KYC exception {run.ticket_id}. You act for {ctx.identity.name} "
                                            f"({ctx.identity.sub}, {ctx.identity.role}). Finish when you are done."}]
    approvals = approvals if approvals is not None else []
    last_obs, limits_built = "", True
    try:
        while True:
            if len(run.steps) >= HARD_CAP:
                run.status = "stopped"
                run.stop_reason = f"Safety cap: {HARD_CAP} steps" + ("" if limits_built else ". check_limits() is not built yet (ENG-902)")
                break
            reply, tin, tout = _model_turn(client, system, messages, ctx, prompt_text, last_obs)
            run.tokens_in += tin
            run.tokens_out += tout
            step = Step(n=len(run.steps) + 1, thought=reply.thought, tool=reply.tool, args=reply.args, tokens_in=tin, tokens_out=tout)
            if reply.tool == "finish":
                run.status = "recorded" if reply.args.get("result") == "recorded" and run.reference else "handed_back"
                run.summary = str(reply.args.get("summary", ""))
                step.decision, step.seconds = "finish", round(time.time() - run.started_at, 1)
                run.steps.append(step)
                break
            action = {"tool": reply.tool, "args": reply.args}
            try:
                reason = check_limits([s.model_dump() for s in run.steps], action, limits, run.started_at, time.time())
            except NotImplementedError:
                reason, limits_built = None, False
            if reason:
                step.decision, step.observation = "stopped", reason
                step.seconds = round(time.time() - run.started_at, 1)
                run.steps.append(step)
                run.status, run.stop_reason = "stopped", reason
                break
            try:
                act, el = actions.plan(ctx, reply.tool, reply.args)
                step.target = act["target"]
                d = gate(act, rules, [a.model_dump() for a in approvals], time.time())
                if d.kind == "ask":
                    shot = None
                    if ctx.screen:
                        shot = str(ctx.shots_dir / f"approval_{len(run.steps) + 1:02d}.png")
                        ctx.screen.shot(Path(shot))
                    ap = Approval(id=f"{run.id}-a{len(approvals) + 1}", run_id=run.id, ticket_id=run.ticket_id, person=run.person,
                                  system=act["system"], tool=act["tool"], target=act["target"], fingerprint=act["fingerprint"],
                                  shows=actions.confirm_rows(ctx), shot=shot, created_at=time.time(),
                                  reason=next((s.thought for s in reversed(run.steps) if s.tool == "choose" and s.args.get("field") == "Outcome"),
                                              reply.thought),
                                  evidence=[f"{s.tool} {next(iter(s.args.values()), '')}".strip() for s in run.steps
                                            if s.tool in actions.BANK_TOOLS or s.tool == "open_caseflow"])
                    approvals.append(ap)
                    run.approvals.append(ap.id)
                    run.status = "waiting_approval"
                    save(run)
                    decided = approver(ap)
                    approvals[-1] = decided
                    if decided.status == "pending":  # Day 10: the workflow keeps the proposal and waits; this run ends here
                        step.decision = "asked"
                        step.observation = f"Waiting for {run.person}'s approval: the case workflow keeps the proposal"
                        step.seconds = round(time.time() - run.started_at, 1)
                        run.steps.append(step)
                        run.outcome = ctx.chosen.get("Outcome", "")
                        run.reason_code = ctx.chosen.get("Reason code", "")[:3]
                        run.summary = f"Proposed {run.outcome} ({run.reason_code}): waiting for {run.person}"
                        break
                    run.status = "running"
                    if decided.status in ("rejected", "expired"):
                        step.decision = decided.status
                        step.observation = f"{decided.status.capitalize()} by {decided.decided_by}: {decided.note}".strip()
                        step.seconds = round(time.time() - run.started_at, 1)
                        run.steps.append(step)
                        if run.mode == "shadow":
                            run.status = "proposed"
                            run.outcome = ctx.chosen.get("Outcome", "")
                            run.reason_code = ctx.chosen.get("Reason code", "")[:3]
                            run.summary = f"Proposed {run.outcome} ({run.reason_code}); shadow mode writes nothing"
                        else:
                            run.status = "rejected" if decided.status == "rejected" else "stopped"
                            run.stop_reason = step.observation
                        break
                    d = gate(act, rules, [a.model_dump() for a in approvals], time.time())
                if d.kind == "deny":
                    step.decision, obs = "denied", f"Refused by the gate: {d.reason}"
                else:
                    step.decision = "approved" if any(a.fingerprint == act["fingerprint"] and a.status == "approved" for a in approvals) else "allow"
                    obs = actions.execute(ctx, reply.tool, reply.args, el)
            except ScreenError as e:
                step.decision, obs = "error", f"Screen error: {e}"
            except ToolRefused as e:
                step.decision, obs = "error", f"Refused by the bank: {e}"
            if ctx.screen and reply.tool in actions.SCREEN_TOOLS and step.decision not in ("denied",):
                p = ctx.shots_dir / f"step_{step.n:02d}.png"
                try:
                    ctx.screen.shot(p)
                    step.shot = p.name
                except Exception:
                    pass
            step.observation = obs
            step.seconds = round(time.time() - run.started_at, 1)
            run.steps.append(step)
            ctx.facts["chosen"] = ctx.chosen
            last_obs = obs
            messages += [{"role": "assistant", "content": reply.model_dump_json()}, {"role": "user", "content": f"Result:\n{obs}"}]
            save(run)
    except Exception as e:  # the run ends with the error on screen, rather than vanishing
        run.status, run.stop_reason = "error", f"{type(e).__name__}: {e}"[:500]
    finally:
        ctx.close()
        run.ended_at = time.time()
        save(run)
    return run
