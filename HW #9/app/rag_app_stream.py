"""Day 9: the chat app, streaming each answer as it is written. Done: you don't need to change it.

Run it:   streamlit run app/rag_app_stream.py
For browser tests without models (in CI):   CHAT_FAKE=1 streamlit run app/rag_app_stream.py

The "Sources:" line appears only when the answer has finished streaming, so tests can wait for it.
"""

import os

import streamlit as st

if os.getenv("CHAT_FAKE") == "1":
    from app.chat_fake import find_sources, stream_answer
else:
    from app.streaming import find_sources, stream_answer

st.set_page_config(page_title="Ask the IT policies")
st.title("Ask the IT policies")
st.caption("Answers come only from the IT policy documents, with the source of each fact.")


def show_sources(sources):
    if sources:
        st.caption("Sources: " + "; ".join(sources))


if "messages" not in st.session_state:
    st.session_state["messages"] = []

for m in st.session_state["messages"]:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m["role"] == "assistant":
            show_sources(m["sources"])

question = st.chat_input("Ask a question about the IT policies", max_chars=4000)
if question:
    st.session_state["messages"].append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        found = find_sources(question)
        text = st.write_stream(stream_answer(found["query"], found["kept"]))
        show_sources(found["sources"])
    st.session_state["messages"].append(
        {"role": "assistant", "content": text, "sources": found["sources"]}
    )
