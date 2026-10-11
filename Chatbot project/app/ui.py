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
from dotenv import load_dotenv

from app import kb
from app.answer import answer_stream
from app.fake_chat import fake_answer_stream, fake_embed, fake_image_answer_stream, fake_stt, fake_ticket, fake_vision
from app.llm import call_image, call_stt
from app.voice import VoiceError, transcribe
from app.llm import call_vision
from app.scanned import estimate, pages_to_read
from app.uploads import UploadError, add_upload, inspect_upload, read_unread_pages
from app.embeddings import embed_documents
from app.illustrate import IllustrationError, illustrate
from app.fake_chat import fake_draw
from app.config import AUDIO_MAX_BYTES, IMAGE_MAX_BYTES, ILLUSTRATIONS_ENABLED, IMAGE_COST_USD, AUDIO_MAX_SECONDS, AUDIO_TYPES, MAX_UPLOAD_BYTES, MAX_VISION_PAGES, TRANSCRIPTS_DIR
from app.images import resize_for_model, thumbnail
from app.screenshot import answer_image_stream
from app.ticket import SEVERITIES, TicketError, make_ticket_logged, to_csv, to_json, validate_ticket
from app.comparison import load_comparison, load_mode_results, meets_target
from app.config import (CHAT_FAKE, IMAGE_THUMBNAIL_SIDE, IMAGE_TYPES, CHUNK_OVERLAP, CHUNK_SIZE, DOCS_DIR, MAX_INPUT_CHARS, MAX_QUESTION_CHARS, MIN_SCORE, RERANK_CANDIDATES,
                        RETRIEVAL_MODE, ROOT, TARGET_HIT_RATE, TARGET_SECONDS, TOP_K)
from app.embeddings import EmbeddingError
from app.evaluate import load_runs
from app.gate import GateError, evaluate, failed_cases, headline, load_history, load_summary, load_thresholds
from app.llm import LLMError
from app.retrieval import MODEL_CALLS, MODES
from app.retrieval_eval import KINDS, check_evidence, load_retrieval_set
from app.retriever import search
from app.safe_text import md_safe
from app.ui_texts import EXAMPLE_QUESTIONS, WELCOME

# What the user sees when something goes wrong
MSG_NO_INDEX = "The knowledge base isn't built yet. Open the Knowledge base tab and click Rebuild index."
MSG_UNREACHABLE = "I couldn't reach the answer service just now. Please try again in a moment, or contact the service desk."
MSG_EMPTY = "Please type a question first."
MSG_REBUILD_FAILED = "The index could not be rebuilt. Please check that Ollama is running, then try again."
MSG_KB_UNREADABLE = "The knowledge base could not be read. Please check the documents folder."
MSG_RESULTS_UNREADABLE = "The saved test results could not be read."
MSG_COMPARISON_UNREADABLE = "The saved retrieval comparison could not be read."
MSG_THRESHOLDS_UNREADABLE = "The evaluation limits (data/eval_thresholds.json) could not be read."
MSG_TICKET_EDIT_INVALID = "That change was not saved: the summary and the next step must be short, plain sentences."
EMPTY_INFO = {"rows": [], "documents": 0, "readable": 0, "chunks": 0, "indexed_chunks": None, "state": "missing"}

KB_NAME = "Northwind IT docs"
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
st.session_state.setdefault("tickets", [])
st.session_state.setdefault("last", None)

st.title("🛠 IT Help Desk Assistant")
if CHAT_FAKE:  # nobody must mistake the fake for the real chatbot
    with st.container(key="fake_banner"):
        st.warning("⚠ FAKE CHATBOT: answers come from a few fixed topics, not from the real documents or models. For testing only.")
st.caption("Answers only from your team's documents · every fact cited")


def esc(text: str) -> str:
    """Escape text before it goes into HTML we build ourselves."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def request_ticket(index: int) -> None:
    """Button callback: remember which answer to make a ticket for; the page makes it on the next run."""
    st.session_state.ticket_request = index


def edit_ticket(index: int, field: str) -> None:
    """Widget callback: keep an edit of one ticket field if the edited ticket is still valid, otherwise put the old value back."""
    ticket = st.session_state.messages[index]["ticket"]
    candidate = {k: ticket[k] for k in ("error_code", "application", "summary", "severity", "next_step")}
    candidate[field] = st.session_state[f"ticket_{field}_{index}"]
    valid, _ = validate_ticket(candidate)
    if valid:
        ticket[field] = valid[field]
    else:
        st.session_state[f"ticket_{field}_{index}"] = ticket[field]
        st.session_state.ticket_notice = MSG_TICKET_EDIT_INVALID


MB = 1024 * 1024  # the upload boxes show their real limits, in megabytes


def pages(n: int) -> str:
    return f"{n} page{'s' if n != 1 else ''}"


def request_illustration(index: int) -> None:
    """Button callback: remember which answer to draw a picture for; the page draws it on the next run."""
    st.session_state.illustration_request = index


def show_illustration_area(msg: dict, index: int) -> None:
    """Only when pictures are switched on: a button, then the picture with its label. Nothing is drawn unless the button is pressed."""
    if not ILLUSTRATIONS_ENABLED or msg.get("declined") or msg.get("refused"):
        return
    made = msg.get("illustration")
    if not made:
        st.button(f"🖼 Draw a picture for this answer (about ${IMAGE_COST_USD:.2f})", key=f"make_illustration_{index}", on_click=request_illustration, args=(index,))
        return
    with st.container(key=f"illustration_{index}"):
        st.image(made["image"], width=320, caption=f"{made['label']} · made from: “{md_safe(made['summary'])}”")


def make_illustration(index: int) -> None:
    message = st.session_state.messages[index]
    with st.spinner("Drawing…"):
        try:
            message["illustration"] = illustrate(message["content"], draw=fake_draw if CHAT_FAKE else call_image)
        except IllustrationError as err:
            st.session_state.ticket_notice = str(err)
        except Exception:  # the picture model could not be reached: a friendly message, never a traceback
            st.session_state.ticket_notice = MSG_UNREACHABLE


def show_ticket_area(msg: dict, index: int) -> None:
    """The "Create ticket" button, or the ticket card with its editable fields and its downloads."""
    ticket = msg.get("ticket")
    if not ticket:
        if msg.get("image_small") and not msg["declined"]:
            st.button("🎫 Create ticket from this screenshot", key=f"make_ticket_{index}", on_click=request_ticket, args=(index,))
        return
    with st.container(key=f"ticket_{index}", border=True):
        st.markdown("**🎫 Ticket from the screenshot**")
        left, right = st.columns(2)
        left.markdown(f"**Error code** &nbsp; `{ticket['error_code'] or 'none'}`")
        right.markdown(f"**Application** &nbsp; {md_safe(ticket['application'] or 'not shown')}")
        st.text_input("Summary", value=ticket["summary"], key=f"ticket_summary_{index}", on_change=edit_ticket, args=(index, "summary"))
        st.selectbox("Severity", list(SEVERITIES), index=list(SEVERITIES).index(ticket["severity"]), key=f"ticket_severity_{index}",
                     format_func=lambda key: f"{key}: {SEVERITIES[key]}", on_change=edit_ticket, args=(index, "severity"))
        st.text_input("Next step", value=ticket["next_step"], key=f"ticket_next_step_{index}", on_change=edit_ticket, args=(index, "next_step"))
        st.caption(("Next step from " + md_safe(ticket["next_step_source"])) if ticket.get("next_step_source")
                   else "Next step written by the model: the documents have no entry for this code.")
        one, two, _ = st.columns([1, 1, 4])
        name = f"ticket_{ticket['error_code'] or 'unknown'}"
        one.download_button("⬇ CSV", to_csv([ticket]), file_name=f"{name}.csv", mime="text/csv", key=f"download_csv_{index}")
        two.download_button("⬇ JSON", to_json([ticket]), file_name=f"{name}.json", mime="application/json", key=f"download_json_{index}")


def make_ticket(index: int) -> None:
    """Make the ticket for the answer at `index` (needs the picture kept in memory with that answer)."""
    message = st.session_state.messages[index]
    with st.spinner("Creating the ticket…"):
        try:
            if CHAT_FAKE:
                ticket = fake_ticket(message.get("image_name", ""))
            else:
                ticket = make_ticket_logged(message["image_small"], message["image_mime"], info=message.get("image_info"))
        except TicketError as err:
            st.session_state.ticket_notice = str(err)
            return
        except Exception:  # the model could not be reached, or anything unexpected: a friendly message, never a traceback
            st.session_state.ticket_notice = MSG_UNREACHABLE
            return
    message["ticket"] = ticket
    st.session_state.tickets.append(ticket)


def show_message(msg: dict, index: int = 0) -> None:
    """Draw one chat message. Each part sits in a container with a key (`user_message_N`, `assistant_message_N`, `badge_N`,
    `answer_N`, `sources_N`, `details_N`), so browser tests can find it without guessing at generated class names."""
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            with st.container(key=f"user_message_{index}"):
                st.markdown(md_safe(msg["content"]))
                if msg.get("image_thumb"):
                    st.image(msg["image_thumb"], width=IMAGE_THUMBNAIL_SIDE, caption=f"{md_safe(msg.get('image_name', 'screenshot'))} · {msg.get('image_pixels', '')} sent to the model")
            return
        with st.container(key=f"assistant_message_{index}"):
            if msg.get("refused"):
                with st.container(key=f"badge_{index}"):
                    st.markdown('<span class="badge-declined">REFUSED</span>', unsafe_allow_html=True)
            elif msg["declined"]:
                with st.container(key=f"badge_{index}"):
                    st.markdown('<span class="badge-declined">DECLINED</span>', unsafe_allow_html=True)
            with st.container(key=f"answer_{index}"):
                st.markdown(md_safe(msg["content"]))  # model text: no links or images
            with st.container(key=f"sources_{index}"):
                if msg["declined"]:
                    st.markdown('<span class="badge-declined">⚠ No sources: nothing relevant was found</span>', unsafe_allow_html=True)
                elif msg["sources"]:
                    tags = "".join(f'<span class="source-tag">[{s["number"]}] {esc(s["source"])} · page {s["page"]}'
                                   f'{" (read by vision)" if s.get("read_by") == "vision" else ""}</span>' for s in msg["sources"])
                    st.markdown(tags, unsafe_allow_html=True)
            with st.container(key=f"details_{index}"):
                reading = msg.get("image_reading")
                if reading and reading.get("error_code"):
                    st.caption(f"Read from the picture: {md_safe(reading['error_code'])}" + (f" · {md_safe(reading['application'])}" if reading.get("application") else ""))
                st.caption(f'{msg["seconds"]} s · {msg["chunks_used"]} chunks')
                if msg.get("shortened_to"):
                    st.caption(f"Long message: only the last part was used ({len(msg['shortened_to'])} characters).")
                if msg.get("searched_for"):
                    st.caption(f"Searched for: {md_safe(msg['searched_for'])}")
            show_ticket_area(msg, index)
            show_illustration_area(msg, index)


def write_down_recording() -> None:
    """Button callback: turn the recording into text and put it in the box below, where it can be corrected before it is asked."""
    clip = st.session_state.get("voice_record") or st.session_state.get("voice_upload")
    st.session_state.voice_notice = ""
    if clip is None:
        return
    try:
        heard = transcribe(clip.getvalue(), fake_stt if CHAT_FAKE else call_stt)  # held in memory for this request only
        st.session_state.voice_text = heard["text"]
        st.session_state.voice_info = f"{heard['seconds']:.0f} s of audio · about ${heard['cost_usd']:.4f}" if heard["seconds"] else f"about ${heard['cost_usd']:.4f}"
    except VoiceError as err:
        st.session_state.voice_text, st.session_state.voice_notice = "", str(err)
    except Exception:  # the speech model could not be reached, or anything unexpected: a friendly message, never a traceback
        st.session_state.voice_text, st.session_state.voice_notice = "", MSG_UNREACHABLE


def ask_what_was_heard() -> None:
    """Button callback: the (possibly corrected) text goes down exactly the same path as a typed question."""
    st.session_state.pending = st.session_state.get("voice_text", "")
    st.session_state.voice_text = ""


def show_voice_area() -> None:
    st.caption(f"Record a question, or upload a voice note (up to {AUDIO_MAX_SECONDS} seconds). It is turned into text first, and you can fix the text before it is asked. "
               "The recording is not saved anywhere. Do not record anything you would not type into the chat.")
    st.audio_input("Record a question", key="voice_record")
    st.file_uploader("…or upload a voice note", type=list(AUDIO_TYPES), key="voice_upload", max_upload_size=AUDIO_MAX_BYTES // MB)
    has_clip = bool(st.session_state.get("voice_record") or st.session_state.get("voice_upload"))
    st.button("Write it down", on_click=write_down_recording, disabled=not has_clip, key="voice_transcribe")
    if st.session_state.get("voice_notice"):
        st.warning(st.session_state.voice_notice)
    if st.session_state.get("voice_text"):
        st.text_area("What I heard (fix it if it is wrong)", key="voice_text", max_chars=MAX_QUESTION_CHARS)
        st.caption(st.session_state.get("voice_info", ""))
        st.button("Ask this question", on_click=ask_what_was_heard, type="primary", key="voice_ask")


def stream_answer(question: str, image: tuple[str, bytes] | None = None) -> None:
    """Draw the question and the answer as it is written, then keep both in the conversation.

    While the model writes, the words appear one by one (with a cursor), after a short note ("Searching the documents..." or, with a
    picture, "Reading the screenshot..."). The badge, the sources row and the timing line are drawn only once the whole reply has been
    checked, because those checks need the whole reply. So the timing line is the signal that an answer is finished. If the stream stops
    halfway, the half answer is thrown away and the friendly error is shown instead: a half answer could be missing the step that matters.

    `image` is (file name, bytes) of an attached picture. It is only held in memory for this request; a small preview stays in the
    chat while the page is open. Nothing is written to disk.
    """
    earlier = [m["content"] for m in st.session_state.messages if m["role"] == "user"]
    previous_question = earlier[-1] if earlier else ""  # the previous question comes from the real conversation
    index = len(st.session_state.messages)
    user_message = {"role": "user", "content": question or ("(a screenshot)" if image else "")}
    if image:
        try:
            user_message.update(image_thumb=thumbnail(image[1]), image_name=image[0][:60])
        except Exception:  # a file that is not a picture: the answer function explains it in a friendly message
            pass
    st.session_state.messages.append(user_message)
    slot = st.empty()
    result, text = None, ""

    def fail(message: str) -> None:
        slot.empty()
        show_message(st.session_state.messages[index], index)  # the question stays visible, with the error under it
        st.error(message)

    if image and CHAT_FAKE:
        events = fake_image_answer_stream(question, image[1], image[0], previous_question=previous_question)
    elif image:
        events = answer_image_stream(question, image[1], image[0], previous_question=previous_question)
    else:
        events = (fake_answer_stream if CHAT_FAKE else answer_stream)(question, previous_question=previous_question)
    try:
        with slot.container():
            with st.chat_message("user"), st.container(key="stream_user"):
                st.markdown(md_safe(user_message["content"]))
                if user_message.get("image_thumb"):
                    st.image(user_message["image_thumb"], width=IMAGE_THUMBNAIL_SIDE)
            with st.chat_message("assistant"):
                with st.container(key="stream_text"):
                    live = st.empty()
                live.caption("Reading the screenshot…" if image else "Searching the documents…")
                for kind, value in events:
                    if kind == "piece":
                        text += value
                        live.markdown(md_safe(text) + " ▌")  # model text: no links or images
                    elif kind == "status":
                        live.caption(value)
                    else:
                        result = value
    except ValueError:
        return fail(MSG_NO_INDEX)
    except (EmbeddingError, LLMError):
        return fail(MSG_UNREACHABLE)
    except Exception:  # anything unexpected: show a friendly message, never a traceback or a path
        return fail(MSG_UNREACHABLE)
    if result.get("image_info"):
        user_message["image_pixels"] = result["image_info"]["pixels"]
    reply = {
        "role": "assistant",
        "content": result["answer"],
        "declined": result["declined"],
        "refused": result.get("refused", False),
        "sources": result["sources"],
        "seconds": result["seconds"],
        "chunks_used": result["chunks_used"],
        "searched_for": result.get("searched_for", ""),
        "shortened_to": result.get("shortened_to", ""),
        "image_reading": result.get("image"),
        "image_info": result.get("image_info"),
    }
    if image and result.get("image"):
        try:
            reply["image_small"], reply["image_mime"], _ = resize_for_model(image[1])  # in memory only, for "Create ticket"
            reply["image_name"] = image[0][:60]
        except Exception:
            pass
    st.session_state.messages.append(reply)
    st.session_state.last = result
    slot.empty()  # the live version goes, and the finished messages (badge, sources, timing) are drawn in its place
    show_message(st.session_state.messages[index], index)
    show_message(reply, index + 1)


def split_input(value) -> tuple[str | None, list]:
    """What the chat box returned: plain text, or text with attached files. Returns (text, files); (None, []) when nothing was sent."""
    if value is None:
        return None, []
    if isinstance(value, str):
        return value, []
    return (getattr(value, "text", "") or ""), list(getattr(value, "files", []) or [])


def ask_example(text: str) -> None:
    """Button callback: remember the clicked example so the next run asks it."""
    st.session_state.pending = text


def clear_chat() -> None:
    st.session_state.messages = []
    st.session_state.tickets = []
    st.session_state.last = None
    st.session_state.pending = None


tab_chat, tab_kb, tab_tests, tab_retrieval, tab_evaluation = st.tabs(["Chat", "Knowledge base", "Test results", "Retrieval", "Evaluation"])

with tab_chat:
    st.subheader("💬 Ask the help desk")
    with st.expander("🎤 Ask by voice"):
        show_voice_area()
    history = st.container()  # drawn after the question is handled, but shown above the input box
    typed = st.chat_input("Ask a question about your IT documents…", max_chars=MAX_INPUT_CHARS, accept_file=True,
                          file_type=sorted(set(IMAGE_TYPES.values()) | {"jpeg"}), max_upload_size=IMAGE_MAX_BYTES // MB)
    clicked = st.session_state.pop("pending", None)  # an example question that was clicked
    asked_for_ticket = st.session_state.pop("ticket_request", None)
    if asked_for_ticket is not None and asked_for_ticket < len(st.session_state.messages):
        make_ticket(asked_for_ticket)
    asked_for_picture = st.session_state.pop("illustration_request", None)
    if asked_for_picture is not None and asked_for_picture < len(st.session_state.messages):
        make_illustration(asked_for_picture)
    if st.session_state.get("ticket_notice"):
        st.warning(st.session_state.pop("ticket_notice"))
    typed_text, typed_files = split_input(typed)
    question = typed_text if typed is not None else clicked
    picture = None
    if typed_files:
        picture = (typed_files[0].name, typed_files[0].getvalue())  # only the first picture; read now, into memory, and kept nowhere else
    if question is not None and not question.strip() and picture is None:
        st.warning(MSG_EMPTY)
        question = None
    with history:
        if not st.session_state.messages and question is None:
            with st.chat_message("assistant"), st.container(key="welcome"):
                st.markdown(WELCOME)
                for i, example in enumerate(EXAMPLE_QUESTIONS):
                    st.button(example, key=f"example_{i}", on_click=ask_example, args=(example,))
        for n, message in enumerate(st.session_state.messages):
            show_message(message, n)
        if question is not None:
            stream_answer(question, picture)

with tab_kb:
    st.subheader("📚 Knowledge base")
    try:
        info = kb.overview()
    except Exception:
        info = EMPTY_INFO
        st.error(MSG_KB_UNREADABLE)
    st.caption(
        f"{info['readable']} of {info['documents']} documents indexed · {info['chunks']} chunks · "
        f"chunk size {CHUNK_SIZE}, overlap {CHUNK_OVERLAP}"
    )
    vision_fn, embed_fn = (fake_vision, fake_embed) if CHAT_FAKE else (call_vision, embed_documents)
    notice = st.session_state.pop("kb_notice", None)  # the result of the last button, kept across the page refresh that follows it
    if notice:
        (st.success if notice[0] == "ok" else st.error)(notice[1])
    waiting = info.get("unread_pages", 0)
    if waiting:
        st.warning(f"{waiting} scanned page{'s' if waiting != 1 else ''} in the knowledge base {'have' if waiting != 1 else 'has'} no text yet, so the chatbot cannot use "
                   f"{'them' if waiting != 1 else 'it'}. Reading them sends each page to the vision model (about ${estimate(waiting)['cost_usd']:.2f} in total).")
        confirmed = estimate(waiting)["needs_confirm"] is False or st.checkbox(f"Yes, read all {waiting} pages (more than {MAX_VISION_PAGES}).", key="confirm_read_remaining")
        if st.button("Read the remaining pages", disabled=not confirmed, key="read_remaining"):
            with st.spinner("Reading scanned pages…"):
                outcome = read_unread_pages(DOCS_DIR, vision_fn, TRANSCRIPTS_DIR)
            if outcome["failed"]:
                st.session_state.kb_notice = ("error", f"Stopped at {outcome['failed'][0]} page {outcome['failed'][1]}: the vision model could not be reached. {pages(outcome['read'])} read and saved; press the button again to carry on.")
            else:
                st.session_state.kb_notice = ("ok", f"Read {pages(outcome['read'])}. Click Rebuild index to use them.")
            st.rerun()
    with st.expander("➕ Add a document (PDF, TXT or MD)"):
        st.caption(f"Up to {MAX_UPLOAD_BYTES // (1024 * 1024)} MB. Pages that are only a picture are read by the vision model, once, and the text is saved. "
                   "Only upload documents that are fine to send to the model provider.")
        upload = st.file_uploader("Choose a document", type=["pdf", "txt", "md"], key=f"kb_upload_{st.session_state.get('upload_round', 0)}", max_upload_size=MAX_UPLOAD_BYTES // MB)
        if upload is not None:
            data = upload.getvalue()
            try:
                plan = inspect_upload(upload.name, data, DOCS_DIR)
            except UploadError as err:
                st.error(str(err))
            else:
                if plan["picture_pages"]:
                    st.info(f"{plan['name']}: {plan['pages']} pages, {plan['picture_pages']} of them scanned. Reading them takes {plan['calls']} vision calls (about ${plan['cost_usd']:.2f}).")
                else:
                    st.info(f"{plan['name']}: {plan['pages']} page{'s' if plan['pages'] != 1 else ''}, read as text. No model call needed.")
                ok = not plan["needs_confirm"] or st.checkbox(f"Yes, spend {plan['calls']} vision calls on this file (more than {MAX_VISION_PAGES}).", key="confirm_upload")
                if st.button("Add to the knowledge base", disabled=not ok, key="add_upload"):
                    with st.spinner("Saving and reading the document…"):
                        done = add_upload(upload.name, data, DOCS_DIR, vision_fn, TRANSCRIPTS_DIR)
                    if done["failed"]:
                        st.session_state.kb_notice = ("error", f"{done['name']} was saved, but the vision model stopped at page {done['failed']}. {pages(len(done['read']))} read and kept; use “Read the remaining pages” to carry on.")
                    else:
                        st.session_state.kb_notice = ("ok", f"{done['name']} added" + (f" and {pages(len(done['read']))} read" if done["read"] else "") + ". Click Rebuild index to use it.")
                    st.session_state.upload_round = st.session_state.get("upload_round", 0) + 1  # a fresh, empty upload box
                    st.rerun()
    left, right, _ = st.columns([1, 1, 4])
    if left.button("↻ Rebuild index", type="primary"):
        with st.spinner("Embedding every chunk…"):
            try:
                total = kb.rebuild(embed_fn=embed_fn)
                st.session_state.kb_notice = ("ok", f"Index rebuilt: {total} chunks.")
                st.rerun()
            except Exception:  # Ollama down, disk problem...: the old index is kept
                st.error(MSG_REBUILD_FAILED)
    if right.button("Open folder"):
        try:
            os.startfile(DOCS_DIR)  # opens on the machine running the app (Windows only)
        except (OSError, AttributeError):
            st.info("The documents are in the data/docs folder of the project.")
    with st.container(key="kb_table"):
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
    st.subheader("🧪 Test results")
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

        with st.container(key="tests_table"):
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
    st.subheader("🔎 Retrieval")
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

        with st.container(key="retrieval_table"):
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

with tab_evaluation:
    st.subheader("📊 Evaluation")
    try:
        thresholds, eval_summary = load_thresholds(), load_summary()
    except GateError:
        thresholds, eval_summary = None, {}
        st.error(MSG_THRESHOLDS_UNREADABLE)
    if thresholds is not None and not eval_summary:
        st.info("No evaluation yet. Run: .venv/Scripts/python.exe -m scripts.run_eval")
    elif thresholds is not None:
        verdict = evaluate(eval_summary, thresholds)
        run = eval_summary.get("run") or {}
        st.caption(f"{run.get('cases', '?')} cases · {len(verdict['dimensions'])} dimensions · run '{md_safe(str(run.get('label', '')))}' in {md_safe(str(run.get('mode', '?')))} mode · "
                   "numbers saved in data/eval_summary.json")
        with st.container(key="eval_verdict"):
            if verdict["ready"]:
                st.success(f"✓ Ready to ship. All {verdict['total']} dimensions are within their limits.")
            else:
                bad = [d["label"] for d in verdict["dimensions"].values() if d["status"] != "PASS"]
                st.error(f"✗ Not ready to ship. {len(bad)} dimension(s) outside their limits: {', '.join(bad)}.")
        names = list(verdict["dimensions"])
        for row_start in range(0, len(names), 3):
            columns = st.columns(3)
            for column, name in zip(columns, names[row_start:row_start + 3]):
                d = verdict["dimensions"][name]
                with column.container(key=f"eval_card_{name}", border=True):
                    colour = {"PASS": "#0b6b57", "FAIL": "#b3261e", "UNTESTED": "#8a6d00"}[d["status"]]
                    st.markdown(f"**{esc(d['label'])}** &nbsp; <span style='color:{colour};font-weight:700'>{d['status']}</span>", unsafe_allow_html=True)
                    st.markdown(f"## {esc(headline(name, d))}")
                    first = d["checks"][0]
                    st.caption(f"{first['metric']} needs {first['op']} {first['limit']}")
                    for extra in d["checks"][1:]:
                        mark = "✓" if extra["passed"] else "✗"
                        st.caption(f"{mark} {extra['metric']}: {'no data' if extra['value'] is None else extra['value']} (needs {extra['op']} {extra['limit']})")
        st.subheader("Failures to look at")
        failures = failed_cases()
        if failures:
            st.caption(f"{len(failures)} case(s) of the last full run did not pass.")
            st.dataframe(pd.DataFrame(failures).rename(columns={"id": "Case", "dimension": "Dimension", "input": "Input", "why": "Why it failed"}),
                         width="stretch", hide_index=True)
        else:
            st.caption("Every case of the last full run passed.")
        with st.expander("Why each limit is where it is"):
            for name in names:
                st.markdown(f"**{esc(verdict['dimensions'][name]['label'])}**: {md_safe(verdict['dimensions'][name]['why'])}")

with st.sidebar:
    st.header("🛠 IT Help Desk Assistant")
    st.caption("Answers from your team's documents")
    st.subheader("KNOWLEDGE BASE")
    badge = {"ready": ("READY", "badge-ready"), "missing": ("NOT BUILT", "badge-warn"), "out of date": ("OUT OF DATE", "badge-warn")}[info["state"]]
    with st.container(key="sidebar_kb_status"):
        st.markdown(f'**{KB_NAME}** <span class="{badge[1]}">{badge[0]}</span>', unsafe_allow_html=True)
        st.caption(f"{info['documents']} documents · {info['chunks']} chunks")
    st.subheader("SETTINGS")
    st.table(pd.DataFrame({"Setting": ["Chunk size", "Overlap", "Chunks retrieved", "Minimum score"],
                           "Value": [str(CHUNK_SIZE), str(CHUNK_OVERLAP), str(TOP_K), f"{MIN_SCORE:.2f}"]}).set_index("Setting"))
    st.subheader("RETRIEVAL MODE")
    with st.container(key="sidebar_mode_chips"):
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
    st.subheader("EVALUATION RUN")
    try:
        sidebar_summary = load_summary()
    except Exception:
        sidebar_summary = {}
    sidebar_run, sidebar_judge = sidebar_summary.get("run") or {}, sidebar_summary.get("judge") or {}
    load_dotenv(ROOT / ".env")
    st.table(pd.DataFrame({
        "Item": ["Suite", "Cases", "Pipeline", "Answer model", "Judge model", "Judge agreement"],
        "Value": ["eval_suite.csv", str(sidebar_run.get("cases", "–")), str(sidebar_run.get("mode", "–")), os.getenv("LLM_MODEL") or "–",
                  os.getenv("JUDGE_MODEL") or "–", f"{sidebar_judge.get('agreement_correct', '–')} · {sidebar_judge.get('agreement_faithful', '–')}"],
    }).set_index("Item"))
    st.subheader("GATE")
    try:
        gate_verdict = evaluate(sidebar_summary, load_thresholds()) if sidebar_summary else None
    except GateError:
        gate_verdict = None
    st.table(pd.DataFrame({
        "Item": ["Thresholds", "Dimensions passing", "Result"],
        "Value": ["eval_thresholds.json", f"{gate_verdict['passing']} / {gate_verdict['total']}" if gate_verdict else "–",
                  ("READY" if gate_verdict["ready"] else "NOT READY (exit 1)") if gate_verdict else "no run yet"],
    }).set_index("Item"))
    gate_history = load_history()
    if gate_history:
        st.caption("GATE HISTORY")
        for n, h in enumerate(gate_history[-6:], start=max(1, len(gate_history) - 5)):
            st.caption(f"Run {n} · {md_safe(h.get('label', ''))} · {h.get('passing', '?')} / {h.get('total', '?')}")
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
    st.subheader("TICKETS THIS SESSION")
    session_tickets = st.session_state.tickets
    if session_tickets:
        st.table(pd.DataFrame([{"Ticket": f"T-{n:03d}", "Code": t["error_code"] or "–", "Severity": t["severity"]} for n, t in enumerate(session_tickets, start=1)]).set_index("Ticket"))
        a, b = st.columns(2)
        a.download_button("⬇ All CSV", to_csv(session_tickets), file_name="tickets.csv", mime="text/csv", key="download_all_csv")
        b.download_button("⬇ All JSON", to_json(session_tickets), file_name="tickets.json", mime="application/json", key="download_all_json")
    else:
        st.caption("No tickets yet. Attach a screenshot, then press Create ticket.")
    st.subheader("LAST QUESTION")
    last = st.session_state.last
    if last:
        st.table(pd.DataFrame({"Measure": ["First words after", "Full answer after", "Chunks used", "Best match score"],
                               "Value": [f"{last.get('first_words_seconds', last['seconds'])} s", f"{last['seconds']} s",
                                         str(last["chunks_used"]), f"{last['best_score']:.2f}"]}).set_index("Measure"))
    else:
        st.caption("Ask a question to see details.")
    st.button("🗑 Clear chat", on_click=clear_chat, disabled=not st.session_state.messages)
