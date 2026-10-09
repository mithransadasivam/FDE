"""Day 9: the plain chat page the browser tests run against (title, answer, "Sources:" line).

Run it:   streamlit run app/rag_app.py
It uses the same answer() as the full app (app/ui.py), without the extra tabs.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # so `import app.*` works

import streamlit as st

from app.answer import answer
from app.config import MAX_QUESTION_CHARS
from app.safe_text import md_safe

# Page header. The browser tests look for this exact title.
st.set_page_config(page_title="Ask the IT policies")
st.title("Ask the IT policies")
st.caption("Answers come only from the IT policy documents, with the source of each fact.")


def show_sources(sources):
    """Under an answer: list its sources, or say the bot declined. The tests check this text."""
    if sources:
        st.caption("Sources: " + "; ".join(md_safe(s) for s in sources))
    else:
        st.caption("No sources: the bot declined.")


# Streamlit re-runs this whole script on every interaction, so the chat history is kept in session_state.
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Redraw the earlier messages (user and assistant) first.
for m in st.session_state["messages"]:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m["role"] == "assistant":
            show_sources(m["sources"])

# The chat box at the bottom; the browser tests find it by this placeholder text.
question = st.chat_input("Ask a question about the IT policies", max_chars=MAX_QUESTION_CHARS)
if question:
    # Save and show the user's question.
    st.session_state["messages"].append({"role": "user", "content": question, "sources": []})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        try:
            # Retrieve the best chunks, ask the model, and apply the decline guards (app/answer.py).
            result = answer(question)
            reply, sources = result["answer"], result["sources"]
        except Exception:  # never show a traceback or a path to the user
            reply, sources = "Sorry, I couldn't answer just now. Please try again.", []
        st.markdown(reply)
        show_sources(sources)
    # Save the answer so it is redrawn on the next run.
    st.session_state["messages"].append({"role": "assistant", "content": reply, "sources": sources})
