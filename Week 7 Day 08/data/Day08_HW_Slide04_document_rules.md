# The bank's document store: how it works and who may see what

*From the bank's platform team. All data is fictional.*

## The API (on the bank's systems, http://localhost:8100)

| Call | Returns |
|---|---|
| `GET /docs/customers/{customer_id}/documents` | `{"documents": [...]}`: every document on that customer's file, as metadata (doc_id, doc_type, received_at, pages) |
| `GET /docs/documents/{doc_id}` | One document's metadata and its content |

Both need a bearer token with **aud = documents** and the scope **kyc.read**. Get one the same way as for the CRM: exchange the person's token (ENG-802).

## Who may see what

- An analyst: documents of their own team's customers.
- A team lead: documents of their region's customers.
- The MLRO: every document.
- A document or customer outside a person's remit answers **404**, as if it did not exist.
- Nobody opens more than **20 documents in an hour**: the 21st answers 429. The store is for checking a case, not for downloading files in bulk.
- Every call is in the bank's audit log, in the person's name.

## For the permission matrix

Three rows, each run as Tom, Grace and Helen:

| id | tool | args | Tom | Grace | Helen |
|---|---|---|---|---|---|
| P8 | list_documents | `{"customer_id": "CU-022578"}` (North 1) | allowed 1 | allowed 1 | allowed 1 |
| P9 | get_document | `{"doc_id": "DS-0075"}` (South 1) | refused | refused | allowed |
| P10 | list_documents | `{"customer_id": "CU-022478"}` (South 1) | refused | refused | allowed 2 |
