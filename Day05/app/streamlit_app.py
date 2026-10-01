"""Day 5, Activity 4: the Smart Document Extractor web app.

Everything works except the download button. Your job: add it where the TODO says.
Run it: ask Claude Code to start it in the background, then open http://localhost:8501
"""

import json

import streamlit as st

from app.extractor import extract_with_retry, get_client

st.set_page_config(page_title="Smart Document Extractor")
st.title("Smart Document Extractor")
st.caption(
    "Upload an invoice as a .txt file. The fields are extracted by a model and validated with Pydantic."
)

uploaded = st.file_uploader("Invoice (.txt)", type=["txt"])

if uploaded is not None:
    text = uploaded.read().decode("utf-8")
    with st.expander("Document text"):
        st.text(text)

    if st.button("Extract fields"):
        with st.spinner("Extracting and validating..."):
            invoice, error, attempts = extract_with_retry(text, get_client())
        # keep the result across reruns (every click reruns the whole script)
        st.session_state["result"] = (invoice, error, attempts, uploaded.name)

if "result" in st.session_state:
    invoice, error, attempts, name = st.session_state["result"]
    if invoice is not None:
        st.success(f"Valid invoice after {attempts} attempt(s)")
        data = invoice.model_dump(mode="json")
        st.json(data)
        # File name from the upload, e.g. Day05_Slide14_invoice_01.txt -> Day05_Slide14_invoice_01.json
        st.download_button(
            "Download JSON",
            data=json.dumps(data, indent=2),
            file_name=name.rsplit(".", 1)[0] + ".json",
            mime="application/json",
        )
    else:
        st.error(
            f"Could not extract a valid invoice after {attempts} attempt(s). A person should review it."
        )
        st.code(error)
