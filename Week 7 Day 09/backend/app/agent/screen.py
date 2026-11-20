"""How the agent sees and works CaseFlow Classic, which has no API (Day 9).

LegacyScreen (done) drives a real browser with Playwright. After every action it reads the page as a list of elements,
like a screen reader would: headings, notices, table rows, and the controls the agent can use, each with its role
(link, button, textbox, combobox) and its accessible name (a button's text, a field's label). The model sees that list
as text (snapshot_text), and acts by naming a control: click "Save", type in "Note".

Ticket ENG-901: find_element() and check_saved() (below).
"""

import re
from pathlib import Path

from app.agent.models import ScreenError

# Collects the page's elements in reading order, and tags each control with data-agent-ref so it can be acted on.
READ_JS = r"""() => {
  const clean = t => (t || '').replace(/\s+/g, ' ').trim();
  const label = el => {
    if (el.id) { const l = document.querySelector(`label[for="${el.id}"]`); if (l) return clean(l.textContent); }
    return clean(el.getAttribute('aria-label') || el.getAttribute('title') || '');
  };
  const out = []; let n = 0;
  for (const el of document.querySelectorAll('h1,h2,h3,p.notice,p.error,p.banner,tr,a[href],input,select,textarea,button')) {
    const tag = el.tagName.toLowerCase(); let role = null, name = '', extra = {};
    if (/^h[1-3]$/.test(tag)) { role = 'heading'; name = clean(el.textContent); }
    else if (tag === 'p') { role = 'text'; name = clean(el.textContent); extra.kind = el.className; }
    else if (tag === 'tr') { role = 'row'; name = [...el.children].map(c => clean(c.textContent)).join(' | '); }
    else if (tag === 'a') { role = 'link'; name = clean(el.textContent); }
    else if (tag === 'button' || (tag === 'input' && ['submit', 'button'].includes(el.type))) { role = 'button'; name = clean(el.value || el.textContent); }
    else if (tag === 'textarea' || (tag === 'input' && ['text', 'password', 'search', ''].includes(el.type))) {
      role = 'textbox'; name = label(el); extra.value = el.value; if (el.maxLength > 0) extra.max = el.maxLength; }
    else if (tag === 'select') { role = 'combobox'; name = label(el);
      extra.value = el.selectedIndex >= 0 ? clean(el.options[el.selectedIndex].text) : '';
      extra.options = [...el.options].map(o => clean(o.text)).filter(Boolean); }
    if (!role) continue;
    const item = { role, name, ...extra };
    if (['link', 'button', 'textbox', 'combobox'].includes(role)) { n += 1; item.ref = 'e' + n; el.setAttribute('data-agent-ref', item.ref); }
    out.push(item);
  }
  return out;
}"""


def snapshot_text(title: str, elements: list[dict]) -> str:
    """The screen as the model reads it (done)."""
    lines = [f"Screen: {title}"]
    for e in elements:
        ref = f"[{e['ref']}] " if e.get("ref") else ""
        line = f'{ref}{e["role"]} "{e["name"]}"'
        if e["role"] == "textbox":
            line += f' = "{e.get("value", "")}"' + (f" (at most {e['max']} characters)" if e.get("max") else "")
        if e["role"] == "combobox":
            line += f' = "{e.get("value", "")}" · options: ' + " | ".join(e.get("options", []))
        lines.append(line)
    return "\n".join(lines)


class LegacyScreen:
    """One browser on CaseFlow Classic, signed in as one person through the bank's single sign-on (done)."""

    def __init__(self, base_url: str):
        self.base = base_url.rstrip("/")
        self._pw = self.browser = self.page = None

    def start(self, caseflow_token: str) -> list[dict]:
        from playwright.sync_api import sync_playwright

        self._pw = sync_playwright().start()
        self.browser = self._pw.chromium.launch()
        ctx = self.browser.new_context(viewport={"width": 760, "height": 520})
        # The token goes in a POST body, never in a URL: URLs end up in logs and browser history
        r = ctx.request.post(f"{self.base}/sso", form={"token": caseflow_token})
        if r.status != 200 or "Main menu" not in r.text():
            raise ScreenError("CaseFlow Classic refused the single sign-on: " + re.sub(r"<[^>]+>", " ", r.text())[:200])
        self.page = ctx.new_page()
        self.page.goto(f"{self.base}/menu")
        return self.read()

    def read(self) -> list[dict]:
        return self.page.evaluate(READ_JS)

    def title(self) -> str:
        return self.page.title().replace("CaseFlow Classic · ", "")

    def act(self, el: dict, kind: str, text: str = "") -> list[dict]:
        loc = self.page.locator(f'[data-agent-ref="{el["ref"]}"]')
        if kind == "click":
            loc.click()
        elif kind == "type":
            loc.fill(text)
        elif kind == "choose":
            loc.select_option(label=text)
        self.page.wait_for_load_state()
        return self.read()

    def shot(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(path), full_page=True)

    def close(self) -> None:
        for x in (self.browser, self._pw):
            try:
                if x is self._pw and x:
                    x.stop()
                elif x:
                    x.close()
            except Exception:
                pass


# ---------------------------------------------------------------- ticket ENG-901


def _norm(t: str) -> str:
    return " ".join((t or "").split()).lower()


def find_element(elements: list[dict], role: str, name: str) -> dict:
    """The one control on this screen with this role and this accessible name.

    ENG-901: find it by what it is, not where it was.
      - Match the role exactly, and the name ignoring case and extra spaces.
      - None found:      raise ScreenError('No button named "Save" on this screen')
      - More than one:   raise ScreenError('2 buttons named "Save" on this screen')
    """
    found = [e for e in elements if e["role"] == role and _norm(e["name"]) == _norm(name)]
    if not found:
        raise ScreenError(f'No {role} named "{name}" on this screen')
    if len(found) > 1:
        raise ScreenError(f'{len(found)} {role}s named "{name}" on this screen')
    return found[0]


def check_saved(elements: list[dict], expected_outcome: str) -> str:
    """After Confirm: the reference CaseFlow gave, if it really recorded the outcome the agent chose.

    ENG-901: read the screen back before saying it worked.
      - The screen must have a heading "Outcome recorded", else
        raise ScreenError('CaseFlow did not confirm the outcome: the screen says "Case withdrawn"') (its first heading)
      - Its notice reads "<outcome> · Reference OUT-40017". If the outcome is not expected_outcome:
        raise ScreenError('CaseFlow recorded "Ready for decision", not "Chase applicant"')
      - Return the reference: "OUT-40017"
    """
    headings = [e["name"] for e in elements if e["role"] == "heading"]
    if not any(_norm(h) == "outcome recorded" for h in headings):
        raise ScreenError(f'CaseFlow did not confirm the outcome: the screen says "{headings[0] if headings else "nothing"}"')
    notice = next((e["name"] for e in elements if e["role"] == "text" and "Reference" in e["name"]), "")
    m = re.search(r"OUT-\d+", notice)
    if not m:
        raise ScreenError("CaseFlow did not confirm the outcome: the screen has no reference")
    recorded = notice.split("·")[0].strip()
    if _norm(recorded) != _norm(expected_outcome):
        raise ScreenError(f'CaseFlow recorded "{recorded}", not "{expected_outcome}"')
    return m.group(0)
