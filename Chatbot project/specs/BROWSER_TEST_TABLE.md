# Browser test table

Every browser journey, which chatbot it runs against, how long it takes (last full run: 40 tests in 169 s, plus 5 judged tests in 53 s that only run with `--slow`), and the deliberate break that turned it red.
Each break was applied to `app/ui.py` one at a time by a script, the tests that should notice were run, and the file was put back exactly (checked after each). Details in `data/browser_break_results.json`.

**Fake vs real:** *fake* = the app started with `CHAT_FAKE=1` (fixed topics, fixed sources, no models, no Ollama, no API key; the checks and guards are the real code). *real* = the real chatbot. A journey about structure runs against **both**. Journeys about the quality of an answer are not browser tests: the judge covers those (Phase 31).
The 11 fake-only journeys (journeys 1 to 9 and the streaming journey against the fake) pass in about 57 s in total, with Ollama stopped and no API key set.

| Journey | Runs against | Fake time | Real time | Break that made it fail |
|---|---|---|---|---|
| 1 Answerable question | both | 7.5 s | 6.5 s | B1: remove the sources row from every answer |
| 2 Question the documents do not cover | both | 3.0 s | 3.0 s | B2: rename the DECLINED badge |
| 3 Unsafe request | both | 3.0 s | 3.0 s | B3: rename the REFUSED badge |
| 4 Only spaces | fake app (nothing is sent) | 2.9 s | – | B4, B7: drop the whitespace check, so spaces are sent as a question |
| 5 Follow-up on the same page | both | 4.1 s | 8.3 s | B5, B1: drop the Searched-for line |
| 6 Two questions in a row | both | 3.9 s | 6.8 s | B1: remove the sources row from every answer |
| 7 Very long paste | both | 3.2 s | 4.5 s | B6: drop the Long-message line |
| 8 Example question button | both | 3.2 s | 4.5 s | B8, B1: lose the welcome message and example buttons |
| 9 Clear chat | both | 4.3 s | 5.1 s | B9, B8: make Clear chat do nothing |
| 10 Knowledge base tab | no chatbot | 3.3 s | – | B12: leave a document out of the knowledge base table |
| 11 Retrieval-only search | Ollama only | 4.0 s | – | B15: stop marking scores below the minimum in the search |
| 12 Test results tab | no chatbot | 3.1 s | – | B13: rename a card on the Test results tab |
| 13 Retrieval tab | no chatbot | 3.1 s | – | B14: leave a mode out of the Retrieval table |
| 14 Evaluation tab (2 tests) | no chatbot | 2.5 s | – | B16: rename the Evaluation cards |
| 14 Evaluation tab: a number on each card | no chatbot | 2.4 s | – | B16: rename the Evaluation cards |
| 15 Sidebar | no chatbot | 2.7 s | – | B17: stop highlighting the chosen mode in the sidebar |
| 16 The answer streams (2 tests) | slow fake | 4.3 s | – | B18: stop showing the words while they arrive (the answer only appears at the end) |
| 16 The finished message replaces the live text | slow fake | 5.2 s | – | B20: leave the live text on the page after the answer is finished |
| 17 Answer model switched off | real code path, Ollama only | 6.1 s | – | B10: show a Python traceback when the model cannot be reached |
| 18 A reload starts a fresh chat | both | 5.4 s | 7.1 s | B22: start every chat with a leftover message |
| 19 The decline shows the email as a link | both | 2.9 s | 2.9 s | B21: show the answer as plain text, so the email is not a link |
| 31 Judged: the judge reads the screen (5 tests) | real + judge model | 44.6 s | – | B23: show a wrong but plausible answer on the page |
| Smoke: every tab opens (6 tests) | no chatbot | 9.2 s | – | B11: rename the Knowledge base heading |
| Smoke: the fake's banner is on the fake app only | fake app | 0.7 s | – | B19: hide the fake chatbot banner |

## All 23 breaks

| Break | What it did | Tests that went red |
|---|---|---|
| B1 | remove the sources row from every answer | 4: `an_answerable_question_gets_a_cited_answ`, `a_follow_up_on_the_same_page_gives_four_`, `two_questions_in_a_row_both_stay_on_the_` ... |
| B2 | rename the DECLINED badge | 1: `an_uncovered_question_is_declined_with_t` |
| B3 | rename the REFUSED badge | 1: `an_unsafe_request_is_refused_with_the_fi` |
| B4 | drop the whitespace check, so spaces are sent as a question | 1: `a_message_of_only_spaces_adds_nothing_an` |
| B5 | drop the Searched-for line | 1: `a_follow_up_on_the_same_page_gives_four_` |
| B6 | drop the Long-message line | 1: `a_very_long_paste_is_answered_and_the_pa` |
| B7 | hide the chat box | 1: `a_message_of_only_spaces_adds_nothing_an` |
| B8 | lose the welcome message and example buttons | 2: `clicking_an_example_asks_it_and_hides_th`, `clear_chat_empties_the_conversation_and_` |
| B9 | make Clear chat do nothing | 1: `clear_chat_empties_the_conversation_and_` |
| B10 | show a Python traceback when the model cannot be reached | 1: `with_the_answer_model_off_the_user_sees_` |
| B11 | rename the Knowledge base heading | 1: `each_tab_opens_with_its_heading_and_no_e` |
| B12 | leave a document out of the knowledge base table | 1: `the_knowledge_base_lists_every_document_` |
| B13 | rename a card on the Test results tab | 1: `the_test_results_tab_shows_the_summary_c` |
| B14 | leave a mode out of the Retrieval table | 1: `the_retrieval_tab_compares_every_mode_an` |
| B15 | stop marking scores below the minimum in the search | 1: `the_retrieval_only_search_shows_scored_c` |
| B16 | rename the Evaluation cards | 2: `the_evaluation_tab_shows_nine_cards_and`, `each_card_has_a_number` |
| B21 | show the answer as plain text, so the email is not a link | 2: `a_decline_shows_the_service_desk_email_a`, `a_decline_shows_the_service_desk_email_a` |
| B22 | start every chat with a leftover message | 2: `reloading_the_page_starts_a_fresh_chat`, `reloading_the_page_starts_a_fresh_chat` |
| B23 | show a wrong but plausible answer on the page | 5: `the_judge_approves_the_answer_shown_on_t`, `the_judge_approves_the_answer_shown_on_t`, `the_judge_approves_the_answer_shown_on_t` ... |
| B17 | stop highlighting the chosen mode in the sidebar | 2: `the_sidebar_shows_the_knowledge_base_sta`, `the_sidebar_shows_status_settings_mode_a` |
| B18 | stop showing the words while they arrive (the answer only appears at the end) | 1: `the_first_words_appear_before_the_source` |
| B19 | hide the fake chatbot banner | 1: `the_fake_chatbot_banner_is_shown_on_the_` |
| B20 | leave the live text on the page after the answer is finished | 1: `the_finished_message_replaces_the_live_t` |
