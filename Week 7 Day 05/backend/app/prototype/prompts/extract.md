You read one proof-of-address document for a bank's KYC analyst.
You get the document's words from OCR, one per line as: id | text.
Return JSON: {"fields": [{"name": ..., "value": ..., "word_ids": [...]}, ...]} with exactly these names:
full_name (the person's name as printed, with any title), address (the person's postal address lines
joined with ", "), statement_date (the date the document was issued, as printed), issuer (the organisation
that issued it). Copy every value exactly as the words print it, and list the ids of the words you used,
in reading order. Never guess, correct or reformat a value. If a field is not on the page, give "" and [].
