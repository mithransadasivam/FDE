"""Which language is a question in? A guess made by plain code (no model, no cost), and the fixed sentences in that language.

The documents are in English and the search model reads English best, so a question in another language is turned into an
English search query (one model call, see app/rewrite.py) and answered in the language it was asked in. The guess is deliberately
careful: anything short, mixed or unclear counts as English, because wrongly treating English as another language would add a
model call and a translation to a question that did not need it.

Spanish, French, German, Portuguese and Italian are recognised by their common small words and accents. A message written mostly
in another script (Chinese, Arabic, Cyrillic, ...) is "other": it is searched through a translation too, and the fixed sentences
stay in English because there is no translation of them.
"""
import re

from app.config import DECLINE_SENTENCE, REFUSAL_SENTENCE

STOPWORDS = {
    "en": "the a an is are was were do does did how what why when where which who can could should would will i my me we you your it its of to in on at for with and or not this that there be have has from by about if as".split(),
    "es": "el la los las un una unos unas es son qué que cómo como cuánto cuándo dónde por para con sin mi mis tu su del al y o no se de en puedo debo hay está están más muy tiene tengo necesito puede pueden sobre entre cuál cuáles quién este esta estos ese esa también pero si ya mío nuevo nueva".split(),
    "fr": "signifie le la les un une des est sont que qui quoi comment combien quand où pourquoi pour avec sans mon ma mes votre du au et ou ne pas de en dans je puis dois faire suis quel quelle quels quelles sur par ce cet cette ces il elle ils vous nous tout tous plus très aussi nouveau nouvelle sont-ils".split(),
    "de": "bedeutet der die das ein eine einen einer einem ist sind wie warum wann wo welche welchen welcher welches kann ich mein meine meinen meiner wir sie es von zu in auf für mit und oder nicht dem den des im muss soll bei nach neuer neue neuen wird werden habe haben hat kein keine auch noch nur wenn dass ob aber wenden bitte".split(),
    "pt": "o a os as um uma é são que como quanto quando onde por para com sem meu minha do da dos das e ou não em posso devo tem está mais muito".split(),
    "it": "il lo la i gli le un uno una è sono che come quanto quando dove perché per con senza mio mia del della e o non in posso devo ha più molto".split(),
}
# a word that belongs to one language only is worth more than a small word two languages share
SHARED = {"a", "o", "e", "en", "la", "no", "de", "es", "un", "una", "i", "in", "le", "me", "die", "der", "do", "pas", "que", "per", "con", "se", "was", "sie", "es", "an", "will", "die"}
ELISION = re.compile(r"(?<![a-z])(?:l|d|qu|j|lorsqu|puisqu|jusqu)['’]\w", re.IGNORECASE)  # French "l'erreur", "qu'est-ce"; English has almost none
ACCENT_HINTS = {"es": "ñ¿¡", "de": "ßäöü", "fr": "çèêëàâîïôùûœ", "pt": "ãõç", "it": "ìòù"}
NAMES = {"en": "English", "es": "Spanish", "fr": "French", "de": "German", "pt": "Portuguese", "it": "Italian", "other": "another language"}

TRANSLATED = {
    "es": {"decline": "No lo sé: los documentos no cubren eso. Por favor, contacta con el servicio de asistencia en la extensión 4357 o en servicedesk@northwind.example.",
           "refusal": "No puedo ayudar con esa petición, porque saltaría un control de seguridad o expondría los datos de otra persona. "
                      "Si tienes una necesidad legítima, contacta con el servicio de asistencia en la extensión 4357 o en servicedesk@northwind.example."},
    "fr": {"decline": "Je ne sais pas : les documents ne couvrent pas cela. Veuillez contacter le service d'assistance au poste 4357 ou à servicedesk@northwind.example.",
           "refusal": "Je ne peux pas aider pour cette demande, car elle contournerait un contrôle de sécurité ou exposerait les données d'une autre personne. "
                      "Si vous avez un besoin légitime, veuillez contacter le service d'assistance au poste 4357 ou à servicedesk@northwind.example."},
    "de": {"decline": "Ich weiß es nicht: Die Dokumente decken das nicht ab. Bitte wenden Sie sich an den Service Desk unter der Durchwahl 4357 oder servicedesk@northwind.example.",
           "refusal": "Dabei kann ich nicht helfen, weil es eine Sicherheitskontrolle umgehen oder die Daten einer anderen Person preisgeben würde. "
                      "Wenn Sie einen echten Bedarf haben, wenden Sie sich bitte an den Service Desk unter der Durchwahl 4357 oder servicedesk@northwind.example."},
}


def words_of(text: str) -> list[str]:
    return re.findall(r"[^\W\d_]+", text.lower())


def detect_language(text: str) -> str:
    """"en", "es", "fr", "de", "pt", "it" or "other" (a different script). Short, mixed or unclear text is "en"."""
    letters = [c for c in text if c.isalpha()]
    if not letters:
        return "en"
    if sum(1 for c in letters if ord(c) > 0x024F) / len(letters) > 0.3:
        return "other"  # mostly a non-Latin script
    words = words_of(text)
    scores = {}
    for code, stop in STOPWORDS.items():
        own = set(stop)
        scores[code] = sum((0.5 if w in SHARED else 1.0) for w in words if w in own)
    scores["fr"] += len(ELISION.findall(text))
    lowered = text.lower()
    for code, marks in ACCENT_HINTS.items():
        scores[code] += 1.5 * sum(1 for c in lowered if c in marks)
    best = max(scores, key=lambda code: scores[code])
    if best == "en" or scores[best] < 1.5 or scores[best] <= scores["en"]:
        return "en"
    return best


def is_english(text: str) -> bool:
    return detect_language(text) == "en"


def localise(sentence_kind: str, language: str) -> str | None:
    """The fixed decline or refusal sentence in this language, or None when there is no translation (it then stays in English)."""
    return TRANSLATED.get(language, {}).get(sentence_kind)


def localise_result(result: dict, language: str) -> dict:
    """Show a decline or refusal in the question's language when a translation exists. The English text is kept as `answer_en`.

    The checks that decide "this is a decline" run on the English sentence before this, so translating it changes only what is shown.
    """
    kind = "refusal" if result.get("refused") else "decline" if result.get("declined") else None
    text = localise(kind, language) if kind else None
    result["language"] = language
    if text:
        result["answer_en"] = result["answer"]
        result["answer"] = text
    return result
