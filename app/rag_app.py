"""Day 6, Activity 4: a chat window for asking questions about the IT policies.

Everything works except showing the sources. Your job: add them where the TODO says.
Run it: ask Claude Code to start it in the background, then open http://localhost:8501
"""

import streamlit as st

from app.rag import answer

st.set_page_config(page_title="Ask the IT policies")
st.title("Ask the IT policies")
st.caption(
    "Answers come only from the five IT policy documents, with the source of each fact."
)

if "messages" not in st.session_state:
    st.session_state["messages"] = []

for m in st.session_state["messages"]:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m["role"] == "assistant":
            if m["sources"]:
                st.caption("Sources: " + "; ".join(m["sources"]))
            else:
                st.caption("No sources: the bot declined.")

question = st.chat_input("Ask a question about the IT policies")
if question:
    st.session_state["messages"].append({"role": "user", "content": question})
    with st.spinner("Searching the policies..."):
        result = answer(question)
    st.session_state["messages"].append(
        {"role": "assistant", "content": result["answer"], "sources": result["sources"]}
    )
    st.rerun()
