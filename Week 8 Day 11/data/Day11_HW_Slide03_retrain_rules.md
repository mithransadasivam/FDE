# When to retrain the small model (agreed with Deborah Okafor and Martin Hale)

The cascade is safe for a kind of document the small model has not learned: it sends the document to the pilot. That costs two Sonnet calls and about 2 seconds for every such document, so the team retrains when a kind keeps going to the pilot.

For each kind of document in a run of the cascade:

| What | How it is counted |
|---|---|
| documents | the documents of that kind |
| to_teacher | the documents of that kind the cascade sent to the pilot because a field was unsure or missing. A spot check is not counted: those documents were sure |
| share | to_teacher ÷ documents, rounded to 3 decimals |
| top_reason | the field named most often in those documents' reasons (a reason starts with the field's name: "statement_date missing", "address 0.61 below 0.70"), or none |
| retrain | yes when share is above 0.5 and there are at least 10 documents of that kind |

The answer is sorted by kind.
