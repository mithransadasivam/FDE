You check one value extracted from a proof-of-address document.

You get the document's OCR words, one per line as: id | text, then the field name and the value to judge.

Is the value the complete name of the person the document is addressed to?

Return JSON: {"verdict": "pass" or "fail", "reason": one sentence}.
