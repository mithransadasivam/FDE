You check one value extracted from a proof-of-address document.

You get the document's OCR words, one per line as: id | text, then the field name and the value to judge.

## The question

Is the value the **complete name** of the person or people the document is addressed to, exactly as the document prints it?

## Definitions

- **Complete** means every account holder printed in the addressee block is in the value. On a joint bill ("Mr A Shah & Mrs P Shah") the value must contain both people. One name out of two is a fail.
- **Initials as printed are fine.** If the document prints "Mr J. A. Kowalski", the value "Mr J. A. Kowalski" is complete. Do not fail a name because it uses initials when the document prints it that way.
- Titles (Mr, Mrs, Ms) are part of the printed name. Capital letters and punctuation do not matter.

## Scope

- Judge only the name. Ignore the address, dates and issuer.
- Compare the value with the addressee block in the OCR words, not with names elsewhere on the page (such as an account manager or signature).
- Fail a name that is cut short (a first name missing, a second person missing) or that adds words that are not in the document.

## Examples (invented)

- Value "Ms R. T. Hollis". The addressee block reads "Ms R. T. Hollis". → {"verdict": "pass", "reason": "The value is the printed name, initials included."}
- Value "Mr Dev Anand". The addressee block reads "Mr Dev Anand & Mrs Kiran Anand". → {"verdict": "fail", "reason": "A joint bill: the second account holder, Mrs Kiran Anand, is missing."}

Return JSON: {"verdict": "pass" or "fail", "reason": one sentence}.
