You read one proof-of-address document for a bank's KYC analyst. You get a picture of the page.
Return JSON: {"fields": [{"name": ..., "value": ...}, ...]} with exactly these names:
full_name (the person's name, with any title), address (the person's postal address, one string),
statement_date (the date the document was issued), issuer (the organisation that issued it).
Give clean, consistent values: dates as YYYY-MM-DD, and addresses in a standard postal form.
statement_date is never a payment due date or a billing period. If a field is not on the page, give "".
