"""The two ways to read a document (done: you do not change this file for a ticket).

parser: parse the document into words (ENG-601), send the words to the model with an extraction prompt such as
        extract_v2 (Day 4), and ground each value on the words the model cites (Day 3's ground_fields).
vision: send a picture of the page to the model with a vision prompt such as extract_vlm_v0. A picture has no
        word ids, so each value is grounded afterwards by finding it among the parsed words (locate_value).

Each reply is kept in engagement/pipeline/<prompt>/<doc_id>.json, so a document is read once per prompt and model.
"""

import re
import time

from app import store
from app.llm import ask_json
from app.pipeline.documents import page_image
from app.pipeline.parse import parse_document
from app.prototype.grounding import CHECK_AT, OK_AT, status_for, union_box
from app.prototype.grounding import ground_fields
from app.prototype.models import FIELD_LABELS, FIELDS, ExtractionReply, Field, OcrWord
from app.prototype.cases import load_prompt

METHODS = {"parser": "Parser + LLM", "vision": "Vision model"}


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (text or "").lower())


def method_of(prompt: str) -> str:
    """extract_vlm_* prompts are vision prompts; every other extraction prompt reads words."""
    return "vision" if prompt.startswith("extract_vlm") else "parser"


def locate_value(value: str, words: list[OcrWord], max_gap: int = 8) -> list[str]:
    """The ids of the words that spell `value`, in order, allowing other words in between (a digital PDF's reading
    order can interleave two columns). Each piece of the value must match one word exactly (letters and digits only).
    Returns [] when the value cannot be found."""
    pieces = [p for p in (norm(t) for t in re.split(r"[\s,]+", value or "")) if p]
    if not pieces:
        return []
    texts = [norm(w.text) for w in words]
    for start, t in enumerate(texts):
        if t != pieces[0]:
            continue
        ids, pos, ok = [words[start].id], start, True
        for p in pieces[1:]:
            nxt = next((j for j in range(pos + 1, min(len(texts), pos + 1 + max_gap)) if texts[j] == p), None)
            if nxt is None:
                ok = False
                break
            ids.append(words[nxt].id)
            pos = nxt
        if ok:
            return ids
    return []


def ground_located(reply: ExtractionReply, words: list[OcrWord], ok_at: float = OK_AT, check_at: float = CHECK_AT) -> list[Field]:
    """Fields for a reply without word ids: find each value on the page, then judge it like any grounded field."""
    by_id = {w.id: w for w in words}
    given = {f.name: f for f in reply.fields}
    out = []
    for name in FIELDS:
        f = given.get(name)
        label = FIELD_LABELS[name]
        if f is None or not f.value.strip():
            out.append(Field(name=name, label=label, value="", confidence=0.0, status="missing", note="Not found on the page"))
            continue
        ids = locate_value(f.value, words)
        if not ids:
            out.append(Field(name=name, label=label, value=f.value, confidence=0.0, status="not_on_page",
                             note="This value is not printed on the page"))
            continue
        cited = [by_id[i] for i in ids]
        conf = round(min(w.confidence for w in cited), 2)
        out.append(Field(name=name, label=label, value=f.value, confidence=conf, status=status_for(conf, ok_at, check_at),
                         box=union_box([w.box for w in cited]), page_text=" ".join(w.text for w in cited)))
    return out


def scripted_latency_ms(tokens_in: int, tokens_out: int) -> int:
    """How long a call takes on the scripted model: a fixed start, plus reading the input and writing the output."""
    return round(600 + 0.45 * tokens_in + 8 * tokens_out)


def read(doc_id: str, prompt: str, client, force: bool = False) -> dict:
    """Read one document with one prompt. Returns {"doc_id", "prompt", "method", "source", "fields", "usage"}.
    The reply is kept; force=True asks the model again (the Batch tab does, to measure real throughput)."""
    tag = getattr(client, "cache_tag", "")
    name = f"pipeline/{prompt}" + (f"/{tag}" if tag else "") + f"/{doc_id}.json"
    cached = store.load(name, None)
    if cached is not None and not force:
        return cached
    page = parse_document(doc_id)
    method = method_of(prompt)
    started = time.perf_counter()
    if method == "parser":
        lines = "\n".join(f"{w.id} | {w.text}" for w in page.words)
        reply = ask_json(client, load_prompt(prompt), f"Document {doc_id}. OCR words:\n{lines}", ExtractionReply, task=f"{prompt}/{doc_id}")
        fields = ground_fields(reply, page.words)
    else:
        image = page_image(doc_id).read_bytes()
        reply = ask_json(client, load_prompt(prompt), f"Document {doc_id}. The picture of the page is attached.", ExtractionReply,
                         task=f"{prompt}/{doc_id}", image=image)
        fields = ground_located(reply, page.words)
    call = client.calls[-1] if getattr(client, "calls", None) else {}
    tin, tout = call.get("input_tokens", 0), call.get("output_tokens", 0)
    latency = call.get("latency_ms") or (scripted_latency_ms(tin, tout) if call.get("scripted") else round((time.perf_counter() - started) * 1000))
    out = {"doc_id": doc_id, "prompt": prompt, "method": method, "source": page.source, "fields": [f.model_dump() for f in fields],
           "usage": {"input_tokens": tin, "output_tokens": tout, "latency_ms": latency, "scripted": bool(call.get("scripted"))}}
    store.save(name, out)
    return out
