# EVAL_NOTES.md: what each Day 4 evaluation taught us

## Identity swap (prompt 2)
- **What survived into the blind text, and what I decided.** The first run showed that a clue placed *inside* a field the extractor reads
  (the certification list or the education line) reached scoring: a church volunteer group, a women's football club, a parental-leave career
  gap, a "30 years of experience" hobby line and a "they volunteer" sentence. The same clues in a separate INTERESTS section never reached
  the profile at all (the extractor keeps only the fields scoring needs).
- **Decision: yes, `make_blind` should remove them.** `app/privacy.py` now drops a whole line that is only about a personal circumstance
  (religion, parental leave or a family career gap, a women's/men's club, a sports club, a hobby line) instead of trimming it, and treats
  "they / their" like "he / she" as a pronoun proxy. A graduation year in brackets was already removed. After the change no clue reaches the
  blind text and the report lists no findings.
- **Cost of the decision.** A real certification that happens to mention one of these words would be dropped too. That is the safe side of
  the trade (a missed skill is something a person can see; a hidden bias is not), but a recruiter should know it happens.
- **Honest limit.** Fake mode uses rule-based extraction and scoring, so this proves what *reaches* scoring, not how a language model reacts.
  The comparison run (blinding switched off) shows the clue arriving in the unblinded record. Run once with real models.

## Accent test (prompt 3)
- **What went wrong in the worst recording.** The highest word error rate (30.8%) was a short answer spoken fast: "backups or batch jobs" was heard
  as "back up to our batch jobs". The words that fail are the ones that are easy to run together (a list read quickly), not the technical terms.
  The level did not change because the scorer matched the other key words.
- **If one accent were scored lower I would:** not tune the model for that accent first; I would check the transcript for the lost key words,
  show the recruiter the transcript beside the level (the scorecard already does), count how many answers per accent were affected, and
  record it as a finding in the risk register. A level that falls only because of a mis-heard word is sent to a person, never decided by code.
- **What the numbers say.** 6 answers x 7 voices: 0 levels moved. Mean error rate ranged from 1.9% (British, alan) to 8.1% (US, fast), so the
  speech model hears some voices and speeds worse than others even when the level did not move.
- **Honest limit.** These are neural computer voices (Piper), not people. They share one recording quality and no background noise. The scorer
  in fake mode is a keyword counter; with a real model the result could differ. Real accented speech is still untested.
