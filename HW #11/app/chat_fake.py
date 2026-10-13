"""Day 9: a fake chatbot for browser tests in CI, where there is no Ollama and no API key.

Set CHAT_FAKE=1 and the streaming app uses these functions instead of the real ones. It answers
questions that mention a known IT topic (with a citation and a source) and declines the rest,
streaming the words with a short pause, like the real thing. Done: you don't need to change it.
"""

import time

from app.rag import DECLINE

TOPICS = {
    "vpn": ("A VPN session can stay connected for a maximum of 12 hours [1].",
            "Day06_Slide15_policy_vpn_remote_access.pdf, page 1"),
    "password": ("Passwords must be at least 14 characters long [1].",
                 "Day06_Slide15_policy_password_and_accounts.pdf, page 1"),
    "laptop": ("Laptops are replaced every 4 years [1].",
               "Day06_Slide15_policy_equipment_and_use.pdf, page 1"),
    "p1": ("For a P1 incident the response target is 15 minutes [1].",
           "Day06_Slide15_policy_it_support_slas.pdf, page 1"),
}


def find_sources(question: str) -> dict:
    for key, (_, source) in TOPICS.items():
        if key in question.lower():
            return {"query": question, "kept": [key], "sources": [source]}
    return {"query": question, "kept": [], "sources": []}


def stream_answer(question: str, kept: list):
    text = TOPICS[kept[0]][0] if kept else DECLINE
    for word in text.split(" "):
        time.sleep(0.05)
        yield word + " "
