"""Day 18: a first sorting of AI use cases into the EU AI Act's risk categories.

The EU AI Act (Regulation (EU) 2024/1689) sorts AI systems by what they are used for:
    prohibited   practices banned outright (Article 5)
    high         systems in regulated products (Annex I), or used in the areas listed in Annex III
    limited      systems that talk to people or generate content: users must be told (Article 50)
    minimal      everything else: no specific obligations, voluntary codes of conduct

This is a triage tool for a use-case inventory, not legal advice: it asks the questions in the
right order and says which article it relied on. Borderline answers go to a lawyer or the
compliance team, with this output as the starting point.

Dates follow the Digital Omnibus on AI (in force since July 2026), which moved the high-risk
deadlines. Check them again before you rely on them.

Done: the lists, OBLIGATIONS and APPLIES_FROM.
Activity 1: fill in classify_use_case(). Check it with tests/test_ai_act.py.
"""

# Article 5 practices (a selection: the ones a workplace system could plausibly touch)
PROHIBITED = {
    "manipulation": "Article 5(1)(a): manipulative or deceptive techniques that distort behaviour",
    "exploiting_vulnerabilities": "Article 5(1)(b): exploiting age, disability or social situation",
    "social_scoring": "Article 5(1)(c): social scoring",
    "predicting_crime_from_profiling": "Article 5(1)(d): predicting crime from profiling alone",
    "untargeted_face_scraping": "Article 5(1)(e): untargeted scraping of facial images",
    "emotion_recognition_workplace": "Article 5(1)(f): emotion recognition at work or in education",
    "biometric_categorisation_sensitive": "Article 5(1)(g): biometric categorisation by sensitive traits",
    "realtime_remote_biometric_id_public": "Article 5(1)(h): real-time remote biometric identification in public for policing",
}

# Annex III areas: an AI system used in one of these is high-risk (unless Article 6(3) applies)
ANNEX_III = {
    "biometrics": "Annex III point 1: biometrics",
    "critical_infrastructure": "Annex III point 2: critical infrastructure",
    "education": "Annex III point 3: education and vocational training",
    "employment": "Annex III point 4: employment and workers management",
    "essential_services": "Annex III point 5: access to essential services (credit, insurance, benefits)",
    "law_enforcement": "Annex III point 6: law enforcement",
    "migration": "Annex III point 7: migration, asylum and border control",
    "justice_democracy": "Annex III point 8: administration of justice and democratic processes",
}

OBLIGATIONS = {
    "prohibited": ["Do not build or use it"],
    "high": [
        "Risk management system and technical documentation",
        "Data governance, logging and record-keeping",
        "Human oversight, accuracy, robustness and cybersecurity",
        "Conformity assessment, registration and post-market monitoring",
    ],
    "limited": [
        "Tell people they are talking to an AI system (Article 50(1))",
        "Mark generated content as AI-generated where Article 50 requires it",
    ],
    "minimal": ["No specific obligations; follow a voluntary code of conduct"],
}

APPLIES_FROM = {
    "prohibited": "2 February 2025",
    "high": "2 December 2027 (Annex III); 2 August 2028 (Annex I)",
    "limited": "2 August 2026",
    "minimal": "-",
}


def classify_use_case(uc: dict) -> dict:
    """The use case's risk category, the reason, and what follows from it.

    uc has these keys (answers to the inventory questionnaire):
        "practices": list of tags         "annex_iii_area": an ANNEX_III key, or None
        "safety_component": bool          "narrow_task": bool (Article 6(3): only a narrow procedural
        "profiles_people": bool            or preparatory task, no real influence on the decision)
        "interacts_with_people": bool     "generates_content": bool

    Rules, IN THIS ORDER: the first that applies decides (tests/test_ai_act.py checks each one):
    1. a tag in uc["practices"] that is in PROHIBITED  -> "prohibited", reason PROHIBITED[tag]
    2. uc["safety_component"]                          -> "high", reason "Article 6(1) and Annex I:
                                                          safety component of a regulated product"
    3. uc["annex_iii_area"] is set, unless (uc["narrow_task"] and not uc["profiles_people"])
                                                       -> "high", reason ANNEX_III[area]
    4. uc["interacts_with_people"] or uc["generates_content"]
                                                       -> "limited", reason "Article 50: transparency"
    5. otherwise                                       -> "minimal", reason "no specific obligations"
    Return {"category": ..., "reason": ..., "obligations": OBLIGATIONS[category],
            "applies_from": APPLIES_FROM[category]}.
    A missing key counts as False, None or an empty list (use uc.get(...)).
    """
    def result(category, reason):
        return {
            "category": category,
            "reason": reason,
            "obligations": OBLIGATIONS[category],
            "applies_from": APPLIES_FROM[category],
        }

    for tag in uc.get("practices") or []:
        if tag in PROHIBITED:
            return result("prohibited", PROHIBITED[tag])
    if uc.get("safety_component"):
        return result(
            "high",
            "Article 6(1) and Annex I: safety component of a regulated product",
        )
    area = uc.get("annex_iii_area")
    if area and not (uc.get("narrow_task") and not uc.get("profiles_people")):
        return result("high", ANNEX_III[area])
    if uc.get("interacts_with_people") or uc.get("generates_content"):
        return result("limited", "Article 50: transparency")
    return result("minimal", "no specific obligations")
