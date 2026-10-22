"""Day 12: the research agent's tools. Done: nothing to fill in here.

The agent can read, never change: Day 11's reading tools, a web search over vendor support articles
(a fixed set of fictional articles, so everyone gets the same results), and a notebook.
"""

import json
from datetime import date
from pathlib import Path

from rank_bm25 import BM25Okapi

from app.memory import NoteBook, words
from app.tools import DB_PATH, TOOLS, Tool, _read_only

ARTICLES_FILE = "data/Day12_Slide09_vendor_articles.json"


def _articles(path=ARTICLES_FILE):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def web_search(query: str, k: int = 3, path: str = ARTICLES_FILE) -> dict:
    """Search the vendor support articles. Returns titles, dates, addresses and a short snippet."""
    articles = _articles(path)
    tokens = [sorted(words(a["title"] + " " + a["text"])) for a in articles]
    scores = BM25Okapi(tokens).get_scores(sorted(words(query)))
    best = sorted(range(len(articles)), key=lambda i: scores[i], reverse=True)[:k]
    results = [
        {
            "id": articles[i]["id"],
            "title": articles[i]["title"],
            "published": articles[i]["published"],
            "url": articles[i]["url"],
            "snippet": articles[i]["text"][:160] + "...",
        }
        for i in best
        if scores[i] > 0
    ]
    return {"query": query, "results": results}


def read_article(article_id: str, path: str = ARTICLES_FILE) -> dict:
    """The full text of one article found with web_search."""
    for a in _articles(path):
        if a["id"] == article_id:
            return a
    raise ValueError(f"no article {article_id}; use an id returned by web_search")


def device_age(asset_tag: str, today: str | None = None, db_path: str | None = None) -> dict:
    """A device's purchase date and age in years, from the assets table. Read-only; applies no policy."""
    with _read_only(db_path or DB_PATH) as con:
        row = con.execute(
            "SELECT asset_tag, device_type, model, assigned_to, purchase_date FROM assets WHERE asset_tag = ?",
            [asset_tag],
        ).fetchone()
    if row is None:
        raise ValueError(f"no device with asset tag {asset_tag}; find tags with find_assets")
    bought = date.fromisoformat(row[4])
    now = date.fromisoformat(today) if today else date.today()
    return {
        "asset_tag": row[0],
        "device_type": row[1],
        "model": row[2],
        "assigned_to": row[3],
        "purchase_date": row[4],
        "age_years": round((now - bought).days / 365.25, 1),
    }


DEVICE_AGE_SCHEMA = {
    "name": "device_age",
    "description": "Get one device's purchase date and its age in years, from its asset tag. Find the tag first "
    "with find_assets. For a question about replacement or lifespan, also use search_policies to get the "
    "rule. It only reports the age: it does not apply any replacement rule or policy, and it does not know "
    "warranty.",
    "parameters": {
        "type": "object",
        "properties": {
            "asset_tag": {
                "type": "string",
                "pattern": "^IT-[0-9]{6}$",
                "description": "The asset tag, for example IT-004512",
            },
        },
        "required": ["asset_tag"],
        "additionalProperties": False,
    },
}

WEB_SEARCH_SCHEMA = {
    "name": "web_search",
    "description": "Search vendor support articles on the web for an error code, product or symptom. Returns "
    "titles, publication dates and snippets. Read an article with read_article before relying on it.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "minLength": 3,
                "maxLength": 200,
                "description": 'Keywords, for example "VPN-809 certificate"',
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

READ_ARTICLE_SCHEMA = {
    "name": "read_article",
    "description": "Read the full text of one article returned by web_search, including its publication date.",
    "parameters": {
        "type": "object",
        "properties": {
            "article_id": {
                "type": "string",
                "pattern": "^KB-[0-9]{4}$",
                "description": "For example KB-1101",
            },
        },
        "required": ["article_id"],
        "additionalProperties": False,
    },
}

SAVE_NOTE_SCHEMA = {
    "name": "save_note",
    "description": "Save one useful fact you found, with its source, so you can use it later in this research "
    "and in future sessions. Save facts, not plans.",
    "parameters": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "minLength": 5,
                "maxLength": 300,
                "description": "One fact, in one sentence",
            },
            "source": {
                "type": "string",
                "minLength": 3,
                "maxLength": 100,
                "description": "Where it came from, for example KB-1101, find_tickets or [1] VPN policy",
            },
        },
        "required": ["text", "source"],
        "additionalProperties": False,
    },
}

READ_NOTES_SCHEMA = {
    "name": "read_notes",
    "description": "Look up the notes saved so far, in this session and earlier ones, that match a few keywords.",
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "minLength": 3,
                "maxLength": 200,
                "description": "Keywords to look for",
            },
        },
        "required": ["query"],
        "additionalProperties": False,
    },
}

READ_ONLY = [
    "calculate",
    "service_status",
    "find_tickets",
    "get_ticket",
    "search_policies",
    "find_assets",
]


def agent_tools(notebook: NoteBook) -> dict:
    """The research agent's tools. No tool here can change a ticket: least privilege."""
    tools = {name: TOOLS[name] for name in READ_ONLY}
    tools["device_age"] = Tool(device_age, DEVICE_AGE_SCHEMA)
    tools["web_search"] = Tool(web_search, WEB_SEARCH_SCHEMA)
    tools["read_article"] = Tool(read_article, READ_ARTICLE_SCHEMA)
    tools["save_note"] = Tool(notebook.add, SAVE_NOTE_SCHEMA)
    tools["read_notes"] = Tool(
        lambda query: {"notes": notebook.search(query, 5)}, READ_NOTES_SCHEMA
    )
    return tools
