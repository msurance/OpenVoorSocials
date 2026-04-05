import logging
import anthropic
from django.conf import settings

logger = logging.getLogger(__name__)

_SYSTEM_BASE = """Je bent de sociale media assistent van OpenVoor.app — een Belgisch AI-matchmaking platform voor volwassenen (18+).
OpenVoor is warm, eerlijk en menselijk. De toon is vriendelijk, enthousiast maar nooit overdreven.

Kernwaarden:
- Open voor iedereen vanaf 18 jaar — geen leeftijdsgrens naar boven
- 100% echte mensen, echte connecties
- €5 instapkost om bots buiten te houden
- AI-matching op basis van wie je écht bent, niet op foto's swipen
- 100% GDPR-proof, privacy centraal
- Belgisch, authentiek, warm"""


def _build_system() -> str:
    """Build system prompt, injecting app knowledge base if available."""
    try:
        from apps.params.helpers import get_document
        knowledge = get_document('app.knowledge_base')
    except Exception:
        knowledge = ''
    if knowledge:
        return f"{_SYSTEM_BASE}\n\n---\n\n## Hoe OpenVoor werkt (gebruik dit bij vragen)\n\n{knowledge}"
    return _SYSTEM_BASE

_FB_CODE_PROMPT = """Iemand heeft gereageerd op een Facebook-post van OpenVoor.app met het woord "{keyword}" in hun comment.

Naam: {name}
Hun comment: "{comment}"
Hun kortingscode: {code}

Schrijf een publieke Facebook-reactie (3-4 zinnen) die:
- Warm en persoonlijk begint met hun voornaam
- Uitlegt dat OpenVoor normaal €5 instapkost heeft (om bots buiten te houden) maar dat ze met hun code gratis aansluiten
- De code duidelijk vermeldt: {code}
- Ze stuurt naar https://openvoor.app om zich aan te melden en de code in te voeren
- Eindigend met een warme emoji

Geef ENKEL de reactietekst terug, geen uitleg."""

_NO_CODES_PROMPT = """Iemand heeft gereageerd op een Facebook-post van OpenVoor.app maar alle kortingscodes zijn op.

Naam: {name}
Hun comment: "{comment}"

Schrijf een KORTE publieke reactie (max 2 zinnen) die:
- Empathisch en vriendelijk is
- Zegt dat alle codes voor deze actie op zijn
- Aanmoedigt om de pagina te volgen voor de volgende ronde
- Eindigend met één relevante emoji

Geef ENKEL de reactietekst terug, geen uitleg."""

_IG_CODE_PROMPT = """Iemand heeft gereageerd op een Instagram-post van OpenVoor.app met het woord "{keyword}" in hun comment.

Naam: {name}
Hun comment: "{comment}"
Hun code: {code}

Schrijf een KORTE Instagram-reactie (max 2 zinnen) die:
- Persoonlijk begint met hun voornaam
- De code vermeldt: {code}
- Ze stuurt naar https://openvoor.app
- Compact en emoji-vriendelijk

Geef ENKEL de reactietekst terug, geen uitleg."""

_AI_PROMPT = """Iemand reageert op een post van OpenVoor.app en suggereert of vraagt of de content AI-gegenereerd is.

Naam: {name}
Hun comment: "{comment}"

OpenVoor.app is een community-project van één persoon, gebouwd voor Belgen van alle leeftijden (18+) die écht contact willen.
De content (teksten, afbeeldingen, video's) wordt inderdaad ondersteund door AI — dat is bewust zo gekozen om het project
levensvatbaar te houden als soloproject. De matching-technologie is ook AI-gedreven, maar op volledig geanonimiseerde data.
De mensen op het platform zijn 100% echt.

Schrijf een KORTE, eerlijke en zelfverzekerde reactie (2-3 zinnen) die:
- De AI-ondersteuning bevestigt zonder zich te verontschuldigen
- Uitlegt waarom: community-project, beperkte tijd, AI maakt het haalbaar
- Benadrukt dat de MENSEN op het platform 100% echt zijn
- Warm en licht humoristisch mag zijn
- Eindigend met één emoji

Geef ENKEL de reactietekst terug, geen uitleg."""

_NATURAL_PROMPT = """Iemand heeft een comment geplaatst op een post van OpenVoor.app.

Naam: {name}
Hun comment: "{comment}"
Post context: {post_context}

Schrijf een KORTE, natuurlijke reactie (1-2 zinnen) die:
- Echt en menselijk aanvoelt, niet als een bot
- Inspeelt op wat ze zeggen (stel een vraag, beaam iets, deel empathie)
- Subtiel verbonden is met het thema van OpenVoor (echte connecties, Belgisch, voor iedereen)
- NIET verkoopachtig of promotioneel is
- Eindigend met maximaal één emoji (soms geen)

Geef ENKEL de reactietekst terug, geen uitleg."""


def _call_claude(prompt: str, max_tokens: int = 300) -> str:
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=max_tokens,
        system=_build_system(),
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def generate_fb_reply_with_code(name: str, comment: str, code: str, keyword: str) -> str:
    try:
        return _call_claude(_FB_CODE_PROMPT.format(name=name, comment=comment, code=code, keyword=keyword))
    except Exception as exc:
        logger.error("Claude FB reply generation failed: %s", exc)
        return (
            f"Wat leuk {name}! \U0001f917 Normaal betaal je \u20ac5 instapkost (om bots buiten te houden) \u2014 "
            f"maar met jouw persoonlijke code sluit je gratis aan \U0001f3ab\n\n"
            f"Jouw code: {code}\n\nGa naar https://openvoor.app en voer je code in bij het aanmelden. Welkom! \u2728"
        )


def generate_no_codes_reply(name: str, comment: str, platform: str) -> str:
    try:
        return _call_claude(_NO_CODES_PROMPT.format(name=name, comment=comment))
    except Exception as exc:
        logger.error("Claude no-codes reply generation failed: %s", exc)
        if platform == 'facebook':
            return f"Aah {name}, je bent er net te laat bij! \U0001f625 Alle codes zijn al geclaimd \u2014 volg onze pagina voor de volgende ronde! \U0001f440"
        return f"Aah {name}, te laat! \U0001f625 Alle codes zijn al weg. Volg ons voor de volgende actie \U0001f440"


def generate_ig_reply(name: str, comment: str, code: str, keyword: str) -> str:
    try:
        return _call_claude(_IG_CODE_PROMPT.format(name=name, comment=comment, code=code, keyword=keyword))
    except Exception as exc:
        logger.error("Claude IG reply generation failed: %s", exc)
        return (
            f"Wat leuk {name}! \U0001f917 Jouw code: {code} \u2014 "
            f"maak je profiel aan op https://openvoor.app. Welkom! \u2728"
        )


def generate_ai_acknowledgment(name: str, comment: str) -> str:
    try:
        return _call_claude(_AI_PROMPT.format(name=name, comment=comment))
    except Exception as exc:
        logger.error("Claude AI acknowledgment generation failed: %s", exc)
        return (
            f"Klopt, {name}! \U0001f916 De content wordt ondersteund door AI \u2014 als soloproject is dat de enige manier om dit haalbaar te houden. "
            f"De mensen op het platform zijn wel 100% echt. Eerlijk is eerlijk! \U0001f609"
        )


def generate_natural_reply(name: str, comment: str, post_context: str = '') -> str:
    try:
        return _call_claude(_NATURAL_PROMPT.format(name=name, comment=comment, post_context=post_context or 'een post over echte connecties maken'), max_tokens=150)
    except Exception as exc:
        logger.error("Claude natural reply generation failed: %s", exc)
        return ''
