"""Builds starter_kit/question_bank.json and the diagram bank (8 PNG images + diagrams.json). Fictional (Stage 0)."""
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from scripts.kit.bank_data import BEHAVIOURAL, GUIDE, STAR, TECH

KIT = Path("starter_kit")


def build_question_bank() -> list[dict]:
    bank = []
    for qid, skill, core, diagram, question, points, follow_ups, hint in TECH:
        bank.append({
            "id": qid, "skill": skill, "type": "technical", "core": core, "diagram": diagram, "question": question,
            "key_points": [p[0] for p in points],
            "key_point_detail": [{"text": p[0], "say": p[1], "keywords": p[2]} for p in points],
            "scoring": GUIDE, "follow_ups": follow_ups, "hint": hint,
        })
    for qid, skill, question in BEHAVIOURAL:
        bank.append({"id": qid, "skill": skill, "type": "behavioural", "core": False, "diagram": None, "question": question,
                     "star_checklist": STAR, "scoring": GUIDE,
                     "follow_ups": ["What was your own part in it?", "What was the result, and how do you know?"],
                     "hint": "Use Situation, Task, Action, Result."})
    assert sum(1 for b in bank if b["type"] == "technical") == 40, "the bank must hold 40 technical questions"
    assert sum(1 for b in bank if b["type"] == "behavioural") == 10
    (KIT / "question_bank.json").write_text(json.dumps(bank, indent=1), encoding="utf-8")
    return bank


# ---- diagrams -------------------------------------------------------------------------------------------------------
W, H = 900, 520
COL = {"user": "#e8edf7", "app": "#dff3ea", "data": "#fdebd0", "net": "#ece3f7", "ops": "#fde2e2", "ext": "#f1f1f1"}

DIAGRAMS = {
    "D-01": dict(title="Web service", nodes=[("u", "Users", 40, 220, 110, 60, "user"), ("lb", "Load balancer", 230, 220, 140, 60, "net"),
                 ("a1", "App node 1", 470, 120, 130, 60, "app"), ("a2", "App node 2", 470, 320, 130, 60, "app"),
                 ("db", "Shared database", 700, 220, 150, 60, "data")],
                 edges=[("u", "lb"), ("lb", "a1"), ("lb", "a2"), ("a1", "db"), ("a2", "db")],
                 description="Users reach a load balancer, which spreads traffic over two app nodes. Both app nodes use one shared database.",
                 answer_key=["load balancer spreads traffic", "app tier can scale out", "one shared database is a single point of failure", "database tier is harder to scale"]),
    "D-02": dict(title="CI/CD pipeline", nodes=[("dev", "Developer", 30, 220, 110, 60, "user"), ("git", "Git repo", 180, 220, 110, 60, "ext"),
                 ("b", "Build + unit tests", 330, 220, 150, 60, "ops"), ("s", "Lint + security scan", 520, 120, 170, 60, "ops"),
                 ("r", "Image registry", 520, 320, 150, 60, "data"), ("st", "Staging", 730, 120, 120, 60, "app"), ("p", "Production", 730, 320, 120, 60, "app")],
                 edges=[("dev", "git"), ("git", "b"), ("b", "s"), ("b", "r"), ("s", "st"), ("r", "p")],
                 description="A commit triggers a build with unit tests, a lint and security scan, and an image pushed to a registry, then staging, then production.",
                 answer_key=["build and test on every commit", "scans in the pipeline", "build the image once and promote it", "staging before production"]),
    "D-03": dict(title="Order service", nodes=[("u", "Users", 30, 220, 100, 60, "user"), ("lb", "Load balancer", 180, 220, 130, 60, "net"),
                 ("a1", "App node 1", 370, 110, 120, 60, "app"), ("a2", "App node 2", 370, 330, 120, 60, "app"),
                 ("c", "Cache", 620, 60, 110, 60, "data"), ("db", "Database (single primary)", 600, 220, 220, 70, "data"), ("pay", "Payment API", 620, 400, 150, 60, "ext")],
                 edges=[("u", "lb"), ("lb", "a1"), ("lb", "a2"), ("a1", "c"), ("a1", "db"), ("a2", "db"), ("a2", "pay")],
                 description="Orders go through two app nodes to a single-primary database, with a cache and an external payment API.",
                 answer_key=["orders fail while the primary is down", "add a replica with automatic failover", "health checks", "replication lag can lose data"]),
    "D-04": dict(title="Kubernetes cluster", nodes=[("u", "Users", 30, 220, 100, 60, "user"), ("ing", "Ingress", 170, 220, 110, 60, "net"),
                 ("svc", "Service", 330, 220, 110, 60, "net"), ("p1", "Pod 1 (node A)", 520, 90, 150, 60, "app"), ("p2", "Pod 2 (node B)", 520, 220, 150, 60, "app"),
                 ("p3", "Pod 3 (node B)", 520, 350, 150, 60, "app"), ("cm", "ConfigMap / Secret", 720, 220, 160, 60, "data")],
                 edges=[("u", "ing"), ("ing", "svc"), ("svc", "p1"), ("svc", "p2"), ("svc", "p3"), ("p2", "cm")],
                 description="An ingress sends traffic to a service, which spreads it over three pods on two nodes. Pods read a ConfigMap and a Secret.",
                 answer_key=["rolling update behind the service", "readiness probes gate traffic", "node failure reschedules pods", "capacity for rescheduled pods"]),
    "D-05": dict(title="Cloud network", nodes=[("i", "Internet", 30, 220, 100, 60, "user"), ("igw", "Internet gateway", 170, 220, 140, 60, "net"),
                 ("lb", "Load balancer (public subnet)", 350, 100, 220, 60, "net"), ("nat", "NAT gateway (public subnet)", 350, 340, 220, 60, "net"),
                 ("vm", "App VM (private subnet)", 620, 220, 230, 60, "app"), ("db", "Database (data subnet)", 620, 400, 230, 60, "data")],
                 edges=[("i", "igw"), ("igw", "lb"), ("lb", "vm"), ("vm", "nat"), ("nat", "igw"), ("vm", "db")],
                 description="A load balancer sits in a public subnet. App VMs are in a private subnet and reach the internet through a NAT gateway. The database is in a data subnet.",
                 answer_key=["route table sends 0.0.0.0/0 to NAT", "security groups and ACLs", "private subnet needs a NAT gateway", "test with curl, traceroute, DNS"]),
    "D-06": dict(title="Monitoring stack", nodes=[("app", "Application", 40, 220, 130, 60, "app"), ("prom", "Prometheus", 250, 120, 130, 60, "ops"),
                 ("loki", "Log store", 250, 330, 130, 60, "data"), ("gr", "Grafana dashboards", 480, 120, 180, 60, "ops"),
                 ("am", "Alertmanager", 480, 330, 150, 60, "ops"), ("oncall", "On-call engineer", 720, 330, 140, 60, "user")],
                 edges=[("app", "prom"), ("app", "loki"), ("prom", "gr"), ("prom", "am"), ("am", "oncall"), ("loki", "gr")],
                 description="The app exposes metrics to Prometheus and writes logs to a log store. Grafana shows both. Alertmanager notifies the on-call engineer.",
                 answer_key=["golden signals", "dashboards for trends", "alerts on symptoms", "runbooks and low noise"]),
    "D-07": dict(title="Queue and workers", nodes=[("w", "Web app", 40, 220, 120, 60, "app"), ("q", "Queue", 230, 220, 110, 60, "net"),
                 ("w1", "Worker 1", 430, 120, 120, 60, "app"), ("w2", "Worker 2", 430, 320, 120, 60, "app"),
                 ("dlq", "Dead letter queue", 230, 400, 160, 60, "ops"), ("db", "Database", 660, 220, 120, 60, "data")],
                 edges=[("w", "q"), ("q", "w1"), ("q", "w2"), ("w1", "db"), ("w2", "db"), ("q", "dlq")],
                 description="The web app puts jobs on a queue. Two workers process them and write to the database. Failed jobs go to a dead letter queue.",
                 answer_key=["decouples slow work", "workers scale independently", "messages can be lost or duplicated", "retries, dead letter queue, idempotency"]),
    "D-08": dict(title="Two regions", nodes=[("dns", "DNS failover", 380, 20, 140, 50, "net"), ("lbA", "Load balancer A", 90, 130, 150, 55, "net"),
                 ("aA", "App tier A", 90, 250, 150, 55, "app"), ("dbA", "Database primary (region A)", 40, 370, 250, 60, "data"),
                 ("lbB", "Load balancer B", 660, 130, 150, 55, "net"), ("aB", "App tier B (standby)", 640, 250, 190, 55, "app"),
                 ("dbB", "Database replica (region B)", 610, 370, 250, 60, "data")],
                 edges=[("dns", "lbA"), ("dns", "lbB"), ("lbA", "aA"), ("aA", "dbA"), ("lbB", "aB"), ("aB", "dbB"), ("dbA", "dbB")],
                 description="DNS routes users to region A. Region B holds a standby app tier and a replica of the database.",
                 answer_key=["a regional outage makes the region unavailable", "second region with traffic routing", "replicate data across regions", "test failover regularly"]),
}


def _font(size: int):
    for path in ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/segoeui.ttf"):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_diagram(spec: dict, out: Path) -> None:
    img = Image.new("RGB", (W, H), "white")
    d = ImageDraw.Draw(img)
    f, ft = _font(16), _font(22)
    d.text((24, 14), spec["title"], fill="#1b2430", font=ft)
    nodes = {n[0]: n for n in spec["nodes"]}
    for a, b in spec["edges"]:
        _, _, x1, y1, w1, h1, _ = nodes[a]
        _, _, x2, y2, w2, h2, _ = nodes[b]
        p1, p2 = (x1 + w1 / 2, y1 + h1 / 2), (x2 + w2 / 2, y2 + h2 / 2)
        d.line([p1, p2], fill="#5d6b7a", width=3)
        dx, dy = p2[0] - p1[0], p2[1] - p1[1]
        n = (dx * dx + dy * dy) ** 0.5 or 1
        tip = (p2[0] - dx / n * min(w2, h2) * 0.55, p2[1] - dy / n * min(w2, h2) * 0.55)
        d.ellipse([tip[0] - 5, tip[1] - 5, tip[0] + 5, tip[1] + 5], fill="#5d6b7a")
    for _, label, x, y, w, h, kind in spec["nodes"]:
        d.rounded_rectangle([x, y, x + w, y + h], radius=10, fill=COL[kind], outline="#5d6b7a", width=2)
        tw = d.textlength(label, font=f)
        d.text((x + (w - tw) / 2, y + h / 2 - 9), label, fill="#1b2430", font=f)
    img.save(out)


def build_diagram_bank() -> None:
    out = KIT / "diagrams"
    out.mkdir(parents=True, exist_ok=True)
    meta = []
    for did, spec in DIAGRAMS.items():
        draw_diagram(spec, out / f"{did}.png")
        meta.append({"id": did, "title": spec["title"], "file": f"diagrams/{did}.png",
                     "description": spec["description"], "answer_key": spec["answer_key"]})
    (KIT / "diagrams.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


def main() -> None:
    build_question_bank()
    build_diagram_bank()
    print("question bank: 40 technical + 10 behavioural; diagram bank: 8 diagrams")


if __name__ == "__main__":
    main()
