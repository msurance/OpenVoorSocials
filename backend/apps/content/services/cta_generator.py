import logging

import anthropic
from django.conf import settings

logger = logging.getLogger(__name__)

_SYSTEM = """Je bent een sociale media expert voor OpenVoor.app — een Belgisch AI-matchmaking platform voor 30-plussers.
OpenVoor.app helpt mensen die moeite hebben om nieuwe verbindingen te vinden.
Toon: warm, eerlijk, lichtjes humoristisch. Niet te verkoopachtig."""

_CTA_PROMPT = """Schrijf een KORTE CTA-zin (1 zin, max 15 woorden) om toe te voegen aan het einde van deze Facebook/Instagram post.

Categorie: {category}
Post tekst: {copy_nl}
Keyword waarop mensen moeten reageren: {keyword}

De CTA moet:
- Organisch aanvoelen als verlengstuk van de post, niet als reclame
- Mensen uitnodigen om "{keyword}" te commenten voor een persoonlijke kortingscode
- Variëren per categorie (romantisch voor love, avontuurlijk voor travel, sportief voor sports, etc.)
- Max 1 emoji

Voorbeelden van goede CTAs:
- "Klaar voor een échte connectie? Comment MATCH en wij sturen je je persoonlijke code 🎫"
- "Wil jij dit ook beleven? Reageer met OPENVOOR en wij zorgen voor de rest ✨"
- "Nieuwsgierig geworden? Comment KLAAR hieronder 👇"

Geef ENKEL de CTA-zin terug, geen uitleg."""


def generate_cta(category: str, copy_nl: str, keyword: str) -> str:
    """Generate a category-specific, organic CTA using Claude Haiku."""
    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        msg = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=100,
            system=_SYSTEM,
            messages=[{"role": "user", "content": _CTA_PROMPT.format(
                category=category,
                copy_nl=copy_nl[:300],
                keyword=keyword,
            )}],
        )
        return msg.content[0].text.strip()
    except Exception as exc:
        logger.error("CTA generation failed for category %s: %s", category, exc)
        # Fallback per category
        fallbacks = {
            'love': f"Klaar voor een echte connectie? Comment {keyword} en wij sturen je je persoonlijke code 🎫",
            'friends': f"Wil jij dit ook? Reageer met {keyword} hieronder 👇",
            'travel': f"Klaar voor het avontuur? Comment {keyword} en wij zorgen voor de rest ✨",
            'sports': f"Tijd voor actie! Comment {keyword} voor jouw persoonlijke code 💪",
            'parents': f"Herkenbaar? Reageer met {keyword} en wij sturen je iets leuks 🎫",
        }
        return fallbacks.get(category, f"Comment {keyword} voor een persoonlijke kortingscode 🎫")
