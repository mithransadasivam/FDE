"""Day 5, Activity 4: the Smart Document Extractor web app.

Choose a document type (invoice or incident), upload a .txt file and extract it.
Run it: ask Claude Code to start it in the background, then open http://localhost:8501
"""

import json
from pathlib import Path

import streamlit as st

from app.extractor import extract_with_retry, get_client
from app.schemas import SCHEMAS

st.set_page_config(page_title="Smart Document Extractor")
st.title("Smart Document Extractor")

# the schema always comes from this fixed list, never from user input
doc_type = st.selectbox("Document type", list(SCHEMAS), format_func=str.title)
st.caption(
    f"Upload an {doc_type} as a .txt file. "
    "The fields are extracted by a model and validated with Pydantic."
)

uploaded = st.file_uploader(f"{doc_type.title()} (.txt)", type=["txt"])

if uploaded is not None:
    text = uploaded.read().decode("utf-8")
    with st.expander("Document text"):
        st.text(text)

    if st.button("Extract fields"):
        with st.spinner(f"Extracting and validating the {doc_type}..."):
            obj, error, attempts = extract_with_retry(
                text, get_client(), schema=SCHEMAS[doc_type]
            )
        # keep the result across reruns (every click reruns the whole script), with the
        # type it was extracted as, so changing the selector later cannot relabel it
        st.session_state["result"] = (obj, error, attempts, uploaded.name, doc_type)

if "result" in st.session_state:
    obj, error, attempts, name, result_type = st.session_state["result"]
    if obj is not None:
        st.success(f"Valid {result_type} after {attempts} attempt(s)")
        data = obj.model_dump(mode="json")
        st.json(data)
        st.download_button(
            "Download JSON",
            data=json.dumps(data, indent=2),
            file_name=f"{Path(name).stem}.json",
            mime="application/json",
        )
    else:
        st.error(
            f"Could not extract a valid {result_type} after {attempts} attempt(s). "
            "A person should review it."
        )
        st.code(error)
