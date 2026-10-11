# Test Agents review

Playwright has three "Test Agents": a **planner** (explores an app and writes a test plan), a **generator** (turns plan steps into test files) and a **healer** (fixes tests that fail). I set them up for this app and tried each one. This is what they did, what I kept and why.

## How I ran them, and one honest limit

`npx playwright init-agents --loop=claude` wrote the three agent files into `.claude/agents/` and an `.mcp.json` that starts Playwright's test MCP server. **Claude Code loads new agents and MCP servers when a session starts**, so the real agents and their `mcp__playwright-test__*` tools could not be called from the session I was working in. What I did instead: I ran each role as a general-purpose subagent, gave it the generated role prompt file to read and follow as written, and let it drive the browser with Playwright scripts (Python) instead of the MCP tools. Everything else was as the exercise describes: the tests were pointed at the app running with the fake chatbot (`playwright.config.ts`, seed test `tests/agents/seed.spec.ts`).

So this is a review of the agents' *prompts and approach*, run by a stand-in, not of the exact MCP tool experience. The agent files, the seed, the config and `.mcp.json` are kept, so the real agents can be tried in a fresh session. I deliberately did **not** tell the agents my project's rules (structure not wording, no fixed waits, stable locators): the exercise says to review their output against those rules afterwards.

## The planner

It explored the Chat tab and the Knowledge base tab by looking at the live page (24 scenarios, `specs/PLANNER_PLAN.md`; I had asked for 12 to 20).

**What it found that I missed**
- **A real bug in my fake chatbot.** It noticed that after an MFA question, "What is the weather in Paris?" returned the MFA answer, and that "Searched for:" showed "mfa What is the weather in Paris". My fake let a previous topic leak into *any* short question; the real chatbot only rewrites questions that look like follow-ups. I fixed the fake to use the same follow-up check and added a test (`test_an_unrelated_short_question_does_not_borrow_the_previous_topic`).
- Two journeys my plan lacked: **reloading the page starts a fresh chat**, and **the decline's contact email is a link**. Both are now browser tests (journeys 18 and 19).
- Smaller ideas: Enter versus the Send button, wording in capitals, special characters and HTML shown as plain text, odd searches in the knowledge-base search (blank, nonsense).

**What it got wrong or could not do**
- It overshot (24 scenarios), and scenarios 2, 3 and 4 (one per starter button) are nearly the same test three times.
- It could not read the documents table (drawn on a canvas), so it wrote "verify visually". I solved that with the table's row count.
- It wrote scenario 24 (press Rebuild index) from assumptions and flagged it as risky itself. A browser test must not rebuild the real index.
- It treated "the welcome text promises passwords, printers and laptops but the fake declines them" as a possible bug. That is a limit of the *fake*, not of the real chatbot.
- It never saw the other tabs, the streaming, the refusal path, the long-paste note or the model-off error, because it only explored what a first look finds. My plan covers those.
- Its expected results often quote exact on-screen text, which my rules forbid for model answers.

## The generator

I gave it three scenarios (the starter button, the out-of-scope question, Clear chat) and it wrote `tests/agents/chat.spec.ts`, all three passing.

| Rule | Result |
|---|---|
| **No fixed waits** | **Passed.** No `waitForTimeout` anywhere; it relied on `expect(...)` auto-waiting. |
| **Stable locators** | **Mostly passed.** Role, visible text and Streamlit test ids (`stMain`, `stSidebar`, `stChatInputTextArea`). It found that the placeholder uses a "…" character, not three dots, and chose the test id. It also found by itself that Streamlit leaves old elements in the page after a Clear chat or reload and counted only *visible* ones, the same lesson I learned the hard way. |
| **Structure, not wording** | **Failed.** It waited on the fake's exact answer sentences, checked the exact timing text `0.0 s · 0 chunks` (a value that could be 0.01), and the exact score `0.90`. Run against the real chatbot these would fail. |

| Test | What I kept | What I changed or dropped |
|---|---|---|
| Starter button: MFA | The idea: click a starter, the question appears, sources and timing appear, the starters go, the sidebar fills in. | Dropped the exact answer sentence, the exact score and the exact timing text. My Python journey 8 already checks the structure, and the streaming test checks the sidebar's two times. |
| Out-of-scope is declined | The DECLINED badge, no `[n]` citation, the fixed decline sentence (guaranteed by code, so it is structure). | Dropped `0.0 s · 0 chunks`. **Added** the idea of the mailto link (journey 19). |
| Clear chat resets everything | Clear chat brings back the welcome and starters; the button is disabled again. | **Added** "reload starts a fresh chat" as its own journey (18). |

**Decision:** I rewrote the useful scenarios in Python (next to my other browser tests, with the same helpers and keys, and running against both the fake and the real chatbot) and **removed the generated TypeScript tests**, so there is one way to run browser tests, not two. The agent files, the seed, `playwright.config.ts` and `.mcp.json` stay, so the agents can be run again.

## The healer: did it fix the test or hide a bug?

**Experiment 1: a change the app was supposed to allow.** I renamed the "Clear chat" button to "Reset conversation". Two tests failed (the button was not found). The healer inspected the page, found the new name and changed **four lines**, the button's name in the locators (`/Clear chat/` to `/Reset conversation/`). I checked with a diff: that is the only change. **Right call:** a renamed button is a normal change. What it left behind: the test title still says "Clear chat" and one comment is stale, which is harmless but untidy.

**Experiment 2: a real bug.** I changed the app so the button was renamed *and* no longer cleared anything. One test failed (the welcome message never came back). This is the case that matters, because a healer's easiest way out is to weaken the test. **It did not.** It clicked the button three times, saw the old chat still there and the sidebar still filled in, saw that a page reload does reset the page, and reported: "This looks like an application bug, and a test change would only hide it." It made **no change** to the test, did not use `test.fixme()`, and said so. That is the behaviour I wanted.

**What I would still check by hand:** the healer's reasoning is only as good as the plan it sees. It cannot know that "the button should clear the chat" is a *requirement*; it inferred it from the button's name and from the test. A test that is wrong in the same way as the app would be healed to match. So I read every healer change before accepting it, as the exercise says.

## Which one is worth using

- **Planner:** good for a fresh pair of eyes and it found a real bug in my test setup. Treat its plan as a list of ideas, not a plan: prune it and rewrite the expectations as structure.
- **Generator:** a fast first draft with good habits (no fixed waits, sensible locators) and one bad one (exact wording). Always review against the rules.
- **Healer:** fine for renames, careful with real bugs. Always read the diff.
