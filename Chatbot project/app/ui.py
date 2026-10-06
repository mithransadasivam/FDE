"""Streamlit app: Chat, Knowledge base and Test results.

Run (local only): .venv/Scripts/python.exe -m streamlit run app/ui.py --server.address 127.0.0.1
(.streamlit/config.toml also binds it to 127.0.0.1, so the app is not reachable from other computers.)
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so `import app.*` works

import pandas as pd
import streamlit as st

from app import kb
from app.answer import answer
from app.comparison import load_comparison, load_mode_results, meets_target
from app.config import (CHUNK_OVERLAP, CHUNK_SIZE, DOCS_DIR, MAX_QUESTION_CHARS, MIN_SCORE, RERANK_CANDIDATES,
                        RETRIEVAL_MODE, ROOT, TARGET_HIT_RATE, TARGET_SECONDS, TOP_K)
from app.embeddings import EmbeddingError
from app.evaluate import load_runs
from app.llm import LLMError
from app.retrieval import MODEL_CALLS, MODES
from app.retrieval_eval import KINDS, check_evidence, load_retrieval_set
from app.retriever import search
from app.safe_text import md_safe

# What the user sees when something goes wrong
MSG_NO_INDEX = "The knowledge base isn't built yet. Open the Knowledge base tab and click Rebuild index."
MSG_UNREACHABLE = "I couldn't reach the answer service just now. Please try again in a moment, or contact the service desk."
MSG_EMPTY = "Please type a question first."
MSG_REBUILD_FAILED = "The index could not be rebuilt. Please check that Ollama is running, then try again."
MSG_KB_UNREADABLE = "The knowledge base could not be read. Please check the documents folder."
MSG_RESULTS_UNREADABLE = "The saved test results could not be read."
MSG_COMPARISON_UNREADABLE = "The saved retrieval comparison could not be read."
EMPTY_INFO = {"rows": [], "documents": 0, "readable": 0, "chunks": 0, "indexed_chunks": None, "state": "missing"}

KB_NAME = "Northwind IT docs"
WELCOME = (
    "Hi! I answer IT questions using only your team's documents (VPN, MFA, passwords, backups, printers, laptops and more), "
    "and I show where each fact came from. If the documents don't cover something, I'll say so. Try one of these:"
)
EXAMPLE_QUESTIONS = [
    "How do I set up MFA on a new phone?",
    "How long do you keep daily server backups?",
    "My VPN keeps cutting out at home. What can I try?",
]

st.set_page_config(page_title="IT Help Desk Assistant", page_icon="🛠", layout="wide")
st.markdown(
    """<style>
    .badge-declined {background:#fde8e4;color:#b3261e;font-weight:700;font-size:0.75rem;padding:2px 8px;border-radius:6px;}
    .badge-ready {background:#e0f3ee;color:#0b6b57;font-weight:700;font-size:0.75rem;padding:2px 8px;border-radius:6px;}
    .badge-warn {background:#fff1d6;color:#8a5a00;font-weight:700;font-size:0.75rem;padding:2px 8px;border-radius:6px;}
    .chip {background:#2a2d3a;color:#c9cbd6;font-size:0.75rem;padding:2px 8px;border-radius:6px;margin-right:4px;display:inline-block;}
    .chip-on {background:#0b6b57;color:#ffffff;font-weight:700;}
    .source-tag {background:#e0f3ee;color:#0b6b57;font-size:0.8rem;padding:2px 8px;border-radius:6px;margin-right:6px;display:inline-block;}
    </style>""",
    unsafe_allow_html=True,
)

st.session_state.setdefault("messages", [])
st.session_state.setdefault("last", None)

st.title("🛠 IT Help Desk Assistant")
st.caption("Answers only from your team's documents · every fact cited")


def esc(text: str) -> str:
    """Escape text before it goes into HTML we build ourselves."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def show_message(msg: dict) -> None:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(md_safe(msg["content"]))
            return
        if msg["declined"]:
            st.markdown('<span class="badge-declined">DECLINED</span>', unsafe_allow_html=True)
        st.markdown(md_safe(msg["content"]))  # model text: no links or images
        if msg["declined"]:
            st.markdown('<span class="badge-declined">⚠ No sources: nothing relevant was found</span>', unsafe_allow_html=True)
        elif msg["sources"]:
            tags = "".join(f'<span class="source-tag">[{s["number"]}] {esc(s["source"])} · page {s["page"]}</span>' for s in msg["sources"])
            st.markdown(tags, unsafe_allow_html=True)
        st.caption(f'{msg["seconds"]} s · {msg["chunks_used"]} chunks')
        if msg.get("searched_for"):
            st.caption(f"Searched for: {md_safe(msg['searched_for'])}")


def handle_question(question: str) -> None:
    if not question.strip():
        st.warning(MSG_EMPTY)
        return
    # the previous question comes from the real conversation, so "And on a Mac?" can be understood
    earlier = [m["content"] for m in st.session_state.messages if m["role"] == "user"]
    previous_question = earlier[-1] if earlier else ""
    st.session_state.messages.append({"role": "user", "content": question})
    try:
        result = answer(question, previous_question=previous_question)
    except ValueError:
        st.error(MSG_NO_INDEX)
        return
    except (EmbeddingError, LLMError):
        st.error(MSG_UNREACHABLE)
        return
    except Exception:  # anything unexpected: show a friendly message, never a traceback or a path
        st.error(MSG_UNREACHABLE)
        return
    st.session_state.messages.append({
        "role": "assistant",
        "content": result["answer"],
        "declined": result["declined"],
        "sources": result["sources"],
        "seconds": result["seconds"],
        "chunks_used": result["chunks_used"],
        "searched_for": result.get("searched_for", ""),
    })
    st.session_state.last = result


def ask_example(text: str) -> None:
    """Button callback: remember the clicked example so the next run asks it."""
    st.session_state.pending = text


def clear_chat() -> None:
    st.session_state.messages = []
    st.session_state.last = None
    st.session_state.pending = None


tab_chat, tab_kb, tab_tests, tab_retrieval = st.tabs(["Chat", "Knowledge base", "Test results", "Retrieval"])

with tab_chat:
    history = st.container()  # drawn after the question is handled, but shown above the input box
    typed = st.chat_input("Ask a question about your IT documents…", max_chars=MAX_QUESTION_CHARS)
    clicked = st.session_state.pop("pending", None)  # an example question that was clicked
    question = typed if typed is not None else clicked
    if question is not None:
        handle_question(question)
    with history:
        if not st.session_state.messages:
            with st.chat_message("assistant"):
                st.markdown(WELCOME)
                for i, example in enumerate(EXAMPLE_QUESTIONS):
                    st.button(example, key=f"example_{i}", on_click=ask_example, args=(example,))
        for message in st.session_state.messages:
            show_message(message)

with tab_kb:
    try:
        info = kb.overview()
    except Exception:
        info = EMPTY_INFO
        st.error(MSG_KB_UNREADABLE)
    st.caption(
        f"{info['readable']} of {info['documents']} documents indexed · {info['chunks']} chunks · "
        f"chunk size {CHUNK_SIZE}, overlap {CHUNK_OVERLAP}"
    )
    left, right, _ = st.columns([1, 1, 4])
    if left.button("↻ Rebuild index", type="primary"):
        with st.spinner("Embedding every chunk…"):
            try:
                total = kb.rebuild()
                st.success(f"Index rebuilt: {total} chunks.")
                st.rerun()
            except Exception:  # Ollama down, disk problem...: the old index is kept
                st.error(MSG_REBUILD_FAILED)
    if right.button("Open folder"):
        try:
            os.startfile(DOCS_DIR)  # opens on the machine running the app (Windows only)
        except (OSError, AttributeError):
            st.info("The documents are in the data/docs folder of the project.")
    st.dataframe(pd.DataFrame(info["rows"]), width="stretch", hide_index=True)

    st.subheader("🔎 Try a search (retrieval only, no model call)")
    query = st.text_input("Search the knowledge base", placeholder="How long do we keep server backups?")
    if query.strip():
        try:
            for r in search(query, TOP_K):
                below = r["score"] < MIN_SCORE
                note = " *(below the minimum score: not used)*" if below else ""
                st.markdown(f"**{r['score']:.2f}** · `{r['source'].replace(chr(96), chr(39))}` · page {r['page']} · chunk {r['chunk']}{note}")
                st.caption(md_safe(" ".join(r["text"].split())[:220]) + "…")
        except ValueError:
            st.error(MSG_NO_INDEX)
        except Exception:  # embedding service down, index problem...
            st.error(MSG_UNREACHABLE)

try:
    runs = load_runs()
except Exception:
    runs = []
    st.error(MSG_RESULTS_UNREADABLE)

with tab_tests:
    if not runs:
        st.info("No test run yet. Run: .venv/Scripts/python.exe -m scripts.run_tests")
    else:
        labels = [f"Run {r['run']} · minimum score {r['min_score']}" for r in runs]
        picked = runs[labels.index(st.selectbox("Test run", labels[::-1]))]
        s = picked["summary"]
        st.caption(f"Run {picked['run']} · minimum score {picked['min_score']:.2f} · {picked['time']}"
                   + (f" · {md_safe(picked['note'])}" if picked["note"] else ""))
        c1, c2, c3, c4 = st.columns(4)
        def missed(correct: int, total: int):
            """A red '-N missed' marker under a card when something was wrong; nothing when perfect."""
            return None if correct >= total else f"-{total - correct} missed"

        c1.metric("Behaviour correct", f"{s['behaviour_correct']} / {s['total']}",
                  delta=missed(s["behaviour_correct"], s["total"]))
        c2.metric("Answered when it should", f"{s['answered_correctly']} / {s['should_answer']}",
                  delta=missed(s["answered_correctly"], s["should_answer"]))
        c3.metric("Declined when it should", f"{s['declined_correctly']} / {s['should_decline']}",
                  delta=missed(s["declined_correctly"], s["should_decline"]))
        c4.metric("Average time per answer", f"{s['avg_seconds']} s")

        table = pd.DataFrame([{
            "#": r["number"],
            "Question": r["question"],
            "Expected": r["expected"],
            "Bot": "Answered" if r["behaviour"] == "answered" else r["behaviour"].capitalize(),
            "Result": "OK" if r["ok"] else "MISS",
            "Sources": r["sources"] or "–",
        } for r in picked["rows"]])
        def colour_result(value: str) -> str:
            if value == "OK":
                return "background-color:#d9f2e6;color:#0b6b57;font-weight:700;text-align:center"
            return "background-color:#fde8e4;color:#b3261e;font-weight:700;text-align:center"

        st.dataframe(table.style.map(colour_result, subset=["Result"]), width="stretch", hide_index=True)
        st.caption("The score checks behaviour only (answered vs declined). Read each answer and citation yourself.")

        failures = [r for r in picked["rows"] if not r["ok"]]
        if not failures:
            st.success("No failures in this run.")
        for r in failures:
            want = "answered" if r["should_answer"] else "declined"
            st.error(f"✗ Question {r['number']} · should have been {want}")
            st.markdown(
                f"- **Question:** {md_safe(r['question'])}\n"
                f"- **Expected:** {md_safe(r['expected'])}\n"
                f"- **Bot said:** {md_safe(r['answer'] or '(no answer)')}\n"
                f"- **Best match score:** {r['best_score']:.2f} (minimum {picked['min_score']:.2f})\n"
                f"- **Why:** {md_safe(r['reason'] or 'the model answered from the sources it was given')}"
            )

try:
    comparison = load_comparison()
except Exception:
    comparison = []
    st.error(MSG_COMPARISON_UNREADABLE)


def short_sources(text: str, expected: str) -> list[str]:
    """The top sources of one saved row, each marked when it is the expected document."""
    return [(("✓ " if part.startswith(expected + " p.") else "· ") + md_safe(part)) for part in text.split("; ") if part]


with tab_retrieval:
    if not comparison:
        st.info("No retrieval comparison yet. Run: .venv/Scripts/python.exe -m scripts.compare_modes")
    else:
        by_mode = {r["mode"]: r for r in comparison}
        chosen, baseline = by_mode.get(RETRIEVAL_MODE), by_mode.get("vector")
        first = comparison[0]
        st.caption(f"{first['questions']} questions · {len(comparison)} modes · saved to data/retrieval_comparison.csv")
        if chosen:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(f"Hit rate @{chosen['k']} ({chosen['mode']})", f"{chosen['hit_rate']:.0%}")
            c2.metric(f"MRR ({chosen['mode']})", f"{chosen['mrr']:.2f}")
            if baseline:
                c3.metric("Hit rate gained over vector", f"{(chosen['hit_rate'] - baseline['hit_rate']) * 100:+.0f} pts")
            shown_time = chosen["answer_seconds"]
            c4.metric("Time per answer" if shown_time is not None else "Retrieval time",
                      f"{shown_time:.1f} s" if shown_time is not None else f"{chosen['retrieval_ms']} ms")

        def cell(row, kind):
            part = row["by_kind"].get(kind)
            return f"{part['hits']}/{part['total']}" if part else "–"

        table = pd.DataFrame([{
            "Mode": ("✓ " if r["mode"] == RETRIEVAL_MODE else "") + r["mode"],
            f"Hit @{r['k']}": f"{r['hit_rate']:.0%}",
            "MRR": f"{r['mrr']:.2f}",
            **{kind: cell(r, kind) for kind in KINDS},
            "Retrieval ms": r["retrieval_ms"],
            "Model calls": f"{r['calls_per_answer'] - 1} + 1",
            "Answer s": "–" if r["answer_seconds"] is None else f"{r['answer_seconds']:.1f}",
            "Answer or decline": "–" if r["behaviour_total"] is None else f"{r['behaviour_correct']}/{r['behaviour_total']}",
            "Meets target": "yes" if meets_target(r, TARGET_HIT_RATE, TARGET_SECONDS) else "no",
        } for r in comparison])

        def highlight_chosen(row):
            on = row["Mode"].startswith("✓")
            return ["background-color:#d9f2e6;color:#0b6b57;font-weight:700" if on else "" for _ in row]

        st.dataframe(table.style.apply(highlight_chosen, axis=1), width="stretch", hide_index=True)
        st.caption(f"Target (set before measuring): hit rate at least {TARGET_HIT_RATE:.0%} and a whole answer within {TARGET_SECONDS:g} s. "
                   "Model calls: retrieval + the call that writes the answer.")

        st.subheader("🔎 What was found: two modes side by side")
        try:
            questions = load_retrieval_set()
        except Exception:
            questions = []
        modes_available = [m for m in MODES if m in by_mode]
        if questions and len(modes_available) >= 2:
            labels = [f"[{q['kind']}] {q['question'][:80]}" for q in questions]
            pick = questions[labels.index(st.selectbox("Question", labels, index=min(14, len(labels) - 1)))]
            left_col, right_col = st.columns(2)
            default_right = RETRIEVAL_MODE if RETRIEVAL_MODE in modes_available and RETRIEVAL_MODE != "vector" else modes_available[-1]
            for column, default, label in ((left_col, "vector", "Mode A"), (right_col, default_right, "Mode B")):
                mode = column.selectbox(label, modes_available, index=modes_available.index(default), key=f"side_{label}")
                saved = {r["question"]: r for r in load_mode_results(mode)}.get(pick["question"])
                with column:
                    if not saved:
                        st.caption("No saved result for this question and mode.")
                        continue
                    outcome = f"right chunk at rank {saved['rank']}" if saved["rank"] else "right chunk not found"
                    st.markdown(f"**What was found · {md_safe(mode)}** — {outcome}" + (" (hit)" if saved["hit"] == "True" else " (miss)"))
                    if saved.get("searched_for"):
                        st.caption(f"Searched for: {md_safe(saved['searched_for'])}")
                    for line in short_sources(saved["top_sources"], pick["expected_source"]):
                        st.markdown(line)
            st.caption(f"✓ marks the expected document: {md_safe(pick['expected_source'])}. Evidence: “{md_safe(pick['evidence'])}”")

with st.sidebar:
    st.header("🛠 IT Help Desk Assistant")
    st.caption("Answers from your team's documents")
    st.subheader("KNOWLEDGE BASE")
    badge = {"ready": ("READY", "badge-ready"), "missing": ("NOT BUILT", "badge-warn"), "out of date": ("OUT OF DATE", "badge-warn")}[info["state"]]
    st.markdown(f'**{KB_NAME}** <span class="{badge[1]}">{badge[0]}</span>', unsafe_allow_html=True)
    st.caption(f"{info['documents']} documents · {info['chunks']} chunks")
    st.subheader("SETTINGS")
    st.table(pd.DataFrame({"Setting": ["Chunk size", "Overlap", "Chunks retrieved", "Minimum score"],
                           "Value": [str(CHUNK_SIZE), str(CHUNK_OVERLAP), str(TOP_K), f"{MIN_SCORE:.2f}"]}).set_index("Setting"))
    st.subheader("RETRIEVAL MODE")
    st.markdown("".join(f'<span class="chip{" chip-on" if m == RETRIEVAL_MODE else ""}">{m}</span>' for m in MODES), unsafe_allow_html=True)
    st.table(pd.DataFrame({
        "Setting": ["Candidates reranked", "Chunks in the prompt", "Model calls per question"],
        "Value": [str(RERANK_CANDIDATES) if RETRIEVAL_MODE in ("rerank", "full") else "–", str(TOP_K), f"{MODEL_CALLS[RETRIEVAL_MODE]} + 1"],
    }).set_index("Setting"))
    st.subheader("RETRIEVAL TEST SET")
    try:
        test_rows = load_retrieval_set()
        found = len(test_rows) - len(check_evidence(test_rows, DOCS_DIR))
        kinds = " · ".join(str(sum(r["kind"] == k for r in test_rows)) for k in KINDS)
        st.table(pd.DataFrame({
            "Item": ["File", "Questions", "Evidence phrases found", "Kinds (plain · reworded · code · follow-up · messy)"],
            "Value": ["retrieval_test_set.csv", str(len(test_rows)), f"{found} / {len(test_rows)}", kinds],
        }).set_index("Item"))
    except Exception:
        st.caption("The retrieval test set could not be read.")
    st.subheader("DECISION")
    st.table(pd.DataFrame({
        "Item": ["Target", "Chosen mode", "Recorded in"],
        "Value": [f"≥ {TARGET_HIT_RATE:.0%} · under {TARGET_SECONDS:g} s", RETRIEVAL_MODE,
                  "RAG_DECISION.md" if (ROOT / "RAG_DECISION.md").is_file() else "not written yet"],
    }).set_index("Item"))
    st.subheader("LATEST TEST RUN")
    if runs:
        latest = runs[-1]["summary"]
        st.caption(f"Run {runs[-1]['run']} · minimum score {runs[-1]['min_score']:.2f}")
        st.progress(latest["behaviour_correct"] / max(latest["total"], 1))
        st.table(pd.DataFrame({
            "Check": ["Behaviour correct", "Declined correctly", "Answered correctly"],
            "Score": [f"{latest['behaviour_correct']} / {latest['total']}",
                      f"{latest['declined_correctly']} / {latest['should_decline']}",
                      f"{latest['answered_correctly']} / {latest['should_answer']}"],
        }).set_index("Check"))
        if len(runs) > 1:
            st.caption("RUN HISTORY")
            for r in runs:
                st.caption(f"Run {r['run']} · score {r['min_score']:.2f} → {r['summary']['behaviour_correct']} / {r['summary']['total']}")
    else:
        st.caption("No test run yet")
    st.subheader("LAST QUESTION")
    last = st.session_state.last
    if last:
        st.table(pd.DataFrame({"Measure": ["Time taken", "Chunks used", "Best match score"],
                               "Value": [f"{last['seconds']} s", str(last["chunks_used"]), f"{last['best_score']:.2f}"]}).set_index("Measure"))
    else:
        st.caption("Ask a question to see details.")
    st.button("🗑 Clear chat", on_click=clear_chat, disabled=not st.session_state.messages)
