# Day 10 Activity Log

Name: ________________

## Before we start (slide 5)
- Pillow installed; VISION_MODEL, STT_MODEL and IMAGE_MODEL added to .env: ________________

## Activity 1: send an image to a model (slide 9)
- Image tests passing: __ / 5
- Estimated input tokens for the VPN screenshot: ______
- One thing the description got right, and one thing it missed or invented:

## Activity 2: screenshot to ticket (slide 15)
- Triage tests passing: 5 / 5
- Correct fields: error_code 6 / 6   application 6 / 6   severity 4 / 6   valid tickets 6 / 6
- Severity WRONG on 01_vpn and 03_printer: the model said P2, the answer key says P3. Both screenshots show a failure for one user, and P2 means a major service degraded or one team cannot work, so P3 (a single user) fits better. The model over-rated them.
- Which screenshot was hardest, and why:
- Did any reply need the retry?
- Two screenshots that show personal data (slide 14), and what you would crop or cover:

## Activity 3: scanned documents into RAG (slide 21)
- Scanned-page tests passing: 5 / 5
- Chunks from the scanned policy with Day 6's build_index: 0   with build_index_vision: 4
- Answer and source for "How many colour pages can I print each month?": 200 colour pages per month (more needs line manager approval); source Day10_Slide21_policy_printing_scanned.pdf, page 1 (score 0.86)

## Activity 4: voice note to ticket to illustration (slide 26)
- Voice tests passing: __ / 5
- Correct fields: error_code __ / 3   application __ / 3   severity __ / 3

| Voice note | One word the transcript got wrong (or "none") | Ticket right? | Image follows the rules (no text, logos, people)? |
|---|---|---|---|
| 01_vpn | | | |
| 02_printer | | | |
| 03_finance | | | |

- Why does only the ticket's summary go to the image model, not the transcript?
