import logging
import anthropic
from django.conf import settings

logger = logging.getLogger(__name__)

_SYSTEM = """Je bent de sociale media assistent van OpenVoor.app — een Belgisch AI-matchmaking platform voor 30-plussers.
OpenVoor is warm, eerlijk en menselijk. Geen bots, geen nep. De toon is vriendelijk, enthousiast maar nooit overdreven.

Kernwaarden om te verwerken in je antwoorden:
- 100% echte mensen
- €5 instapkost om bots buiten te houden (maar de gebruiker krijgt nu een gratis code)
- AI-matching op basis van wie je écht bent, niet op foto's swipen
- 100% GDPR-proof, privacy centraal
- Belgisch, authentiek, warm"""

_PUBLIC_PROMPT = """Iemand heeft gereageerd op een Facebook-post van OpenVoor.app met het woord "{keyword}" in hun comment.

Naam: {name}
Hun comment: "{comment}"

Schrijf een KORTE publieke reactie (max 2 zinnen) die:
- Warm en persoonlijk begint met hun voornaam
- Zegt dat we ze een privébericht sturen met hun persoonlijke code
- Geen code vermeldt (die komt privé)
- Eindigend met één relevante emoji

Geef ENKEL de reactietekst terug, geen uitleg."""

_PRIVATE_PROMPT = """Iemand heeft gereageerd op een Facebook-post van OpenVoor.app en krijgt een gratis kortingscode.

Naam: {name}
Hun comment: "{comment}"
Hun code: {code}

Schrijf een PRIVÉ Messenger-bericht (3-5 zinnen) dat:
- Persoonlijk en warm begint
- Uitlegt dat ze normaal €5 betalen (om bots buiten te houden) maar nu gratis aansluiten
- De code duidelijk vermeld: {code}
- Ze stuurt naar https://openvoor.app om zich aan te melden en de code in te voeren
- Eindigend met een warme welkomszin

Geef ENKEL de berichttekst terug, geen uitleg."""

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


def _call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text.strip()


def generate_fb_public_reply(name: str, comment: str, keyword: str) -> str:
    try:
        return _call_claude(_PUBLIC_PROMPT.format(name=name, comment=comment, keyword=keyword))
    except Exception as exc:
        logger.error("Claude public reply generation failed: %s", exc)
        return f"Wat leuk dat je reageert, {name}! \U0001f917 We sturen je zo een privébericht met jouw persoonlijke code. Check je inbox! \U0001f4eb"


def generate_fb_private_message(name: str, comment: str, code: str) -> str:
    try:
        return _call_claude(_PRIVATE_PROMPT.format(name=name, comment=comment, code=code))
    except Exception as exc:
        logger.error("Claude private message generation failed: %s", exc)
        return (
            f"Hey {name}! \U0001f917\n\n"
            f"Normaal betaal je \u20ac5 om aan te sluiten \u2014 maar met jouw persoonlijke code sluit je gratis aan \U0001f3ab\n\n"
            f"Jouw code: {code}\n\n"
            f"Ga naar https://openvoor.app, maak je profiel aan en voer de code in. Echte mensen, echte connecties. Welkom! \u2728"
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
