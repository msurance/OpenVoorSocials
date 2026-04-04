import json
import logging
from datetime import datetime, timedelta

import anthropic
from django.conf import settings

logger = logging.getLogger(__name__)

# Rotating USP taglines — one woven organically into each post
TAGLINES = [
    "100% echte mensen — geen bots, geen nep",
    "Slechts 5 euro — precies om robots buiten te houden",
    "Geen foto's swipen, geen eindeloos zoeken — jij krijgt matches op basis van wie je écht bent",
    "100% GDPR-proof — jouw privacy staat centraal",
    "AI-matching op volledig geanonimiseerde data — de app leert jou kennen, niet je profiel",
]

# 12 posts per week — balanced across 5 categories (no klusjes)
CATEGORY_MIX = [
    'love', 'love', 'love', 'love',
    'friends', 'friends',
    'travel', 'travel',
    'sports', 'sports',
    'parents', 'parents',
]

# Two optimal publishing slots for the Belgian 30+ audience
POST_TIMES = ['10:00', '19:00']

SYSTEM_PROMPT = """Je bent een sociale media expert voor OpenVoor.app, een AI-matchmaking platform voor Belgen van 30+.
OpenVoor.app helpt mensen die moeite hebben om nieuwe verbindingen te vinden — voor liefde, vriendschap, sport, reizen en ouderschap.

Schrijf authentieke, warme en herkenbare Nederlandse posts voor Facebook en Instagram.
Doelgroep: Belgen van 30+, mensen die zich soms alleen voelen en op zoek zijn naar echte verbinding.
Toon: warm, eerlijk, niet te commercieel, lichtjes humoristisch waar gepast.
NIET: geen technologisch jargon, geen "algoritme"-taal, geen generieke dating-app clichés.

Elke post moet:
1. Beginnen met een herkenbare situatie of vraag (geen app-reclame als opener)
2. Het opgegeven OpenVoor-kenmerk (tagline) organisch verwerken in de post — niet als los zinnetje eraan plakken, maar als iets dat vanzelfsprekend past in de context
3. Eindigen met een zachte call-to-action richting OpenVoor.app
4. 3-7 relevante Belgische/Nederlandse hashtags bevatten
5. Een concrete, levendige beschrijving bevatten voor een lifestyle foto (image_prompt)

Belangrijk voor image_prompt:
- Beschrijf ALLEEN volwassenen (30-50 jaar) — geen kinderen, geen baby's
- Voor de categorie 'parents': toon de ouder in een gezinscontext via rekwisieten en omgeving
  (speelgoed op tafel, kindertekeningen aan de muur, kleine laarsjes bij de deur, speeltuin op achtergrond)
  maar zet GEEN kinderen in het beeld zelf
- De foto moet realistisch en authentiek aanvoelen, Belgische setting
"""


def _build_schedule(week_start: datetime) -> list[datetime]:
    """
    Return up to 14 scheduled datetime objects for the week.

    Strategy: two posts per day (10:00 + 19:00) across all 7 days starting
    Tuesday, giving exactly 14 posts.  The [:14] cap is a safety guard only.
    """
    schedule = []
    for day_offset in range(1, 8):  # Tuesday through Monday (7 days)
        day = week_start + timedelta(days=day_offset)
        for t in POST_TIMES:
            h, m = map(int, t.split(':'))
            schedule.append(day.replace(hour=h, minute=m, second=0, microsecond=0))
    return schedule[:14]


def generate_weekly_posts(week_number: int, year: int) -> list[dict]:
    """
    Call the Claude API and return a list of post dicts ready for DB insertion.

    Each dict contains:
        category, copy_nl, hashtags, image_prompt, scheduled_at, week_number, year
    """
    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    # Determine Monday of the requested ISO week
    # ISO week 1 contains the first Thursday of the year; Jan 4 is always in week 1.
    jan4 = datetime(year, 1, 4)
    week_start = jan4 + timedelta(weeks=week_number - 1, days=-jan4.weekday())

    schedule = _build_schedule(week_start)[:len(CATEGORY_MIX)]
    categories = CATEGORY_MIX

    # Assign one rotating tagline per post
    tagged = [
        (categories[i], TAGLINES[i % len(TAGLINES)])
        for i in range(len(categories))
    ]
    post_specs = "\n".join(
        f"{i+1}. categorie: {cat} | tagline om te verwerken: \"{tag}\""
        for i, (cat, tag) in enumerate(tagged)
    )

    user_prompt = (
        f"Genereer {len(categories)} sociale media posts voor de week van "
        f"{week_start.strftime('%d %B %Y')}.\n\n"
        f"Post-specificaties (categorie + tagline per post):\n{post_specs}\n\n"
        f"Geef je antwoord als een JSON-array met exact {len(categories)} objecten, "
        f"elk met deze velden:\n"
        '- "category": één van: love, friends, travel, sports, parents\n'
        '- "copy_nl": de volledige post tekst in het Nederlands (inclusief eventuele emojis) — '
        'verwerk de toegewezen tagline organisch in de tekst\n'
        '- "hashtags": string met hashtags, gescheiden door spaties (3-7 hashtags, mix NL/BE)\n'
        '- "image_prompt": Engelse beschrijving voor een lifestyle foto '
        '(warm, realistisch, 30+ mensen, Belgische setting)\n\n'
        'Geef ALLEEN de JSON array terug, geen andere tekst.'
    )

    logger.info("Generating %d posts for week %d/%d", len(categories), week_number, year)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = message.content[0].text.strip()

    # Strip markdown code fences if Claude wrapped the JSON
    if raw.startswith('```'):
        parts = raw.split('```')
        # parts[1] contains the fenced block; strip language tag if present
        raw = parts[1]
        if raw.startswith('json'):
            raw = raw[4:]
        raw = raw.strip()

    posts_data = json.loads(raw)

    result = []
    for i, post in enumerate(posts_data[:len(categories)]):
        result.append({
            **post,
            'scheduled_at': schedule[i],
            'week_number': week_number,
            'year': year,
        })

    logger.info("Generated %d posts successfully for week %d/%d", len(result), week_number, year)

    return result
