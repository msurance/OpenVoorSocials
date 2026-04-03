import json
import logging
from datetime import datetime, timedelta

import anthropic
from django.conf import settings

logger = logging.getLogger(__name__)

# 14 posts per week — fixed category mix keeps a balanced content calendar
CATEGORY_MIX = [
    'love', 'love', 'love', 'love',
    'friends', 'friends',
    'travel', 'travel',
    'sports', 'sports',
    'parents', 'parents',
    'klusjes', 'klusjes',
]

# Two optimal publishing slots for the Belgian 30+ audience
POST_TIMES = ['10:00', '19:00']

SYSTEM_PROMPT = """Je bent een sociale media expert voor OpenVoor.app, een AI-matchmaking platform voor Belgen van 30+.
OpenVoor.app helpt mensen die moeite hebben om nieuwe verbindingen te vinden — voor liefde, vriendschap, sport, reizen, ouderschap en klusjes.

Schrijf authentieke, warme en herkenbare Nederlandse posts voor Facebook en Instagram.
Doelgroep: Belgen van 30+, mensen die zich soms alleen voelen en op zoek zijn naar echte verbinding.
Toon: warm, eerlijk, niet te commercieel, lichtjes humoristisch waar gepast.
NIET: geen technologisch jargon, geen "algoritme"-taal, geen generieke dating-app clichés.

Elke post moet:
1. Beginnen met een herkenbare situatie of vraag (geen app-reclame als opener)
2. Eindigen met een zachte call-to-action richting OpenVoor.app
3. 3-7 relevante Belgische/Nederlandse hashtags bevatten
4. Een concrete, levendige beschrijving bevatten voor een lifestyle foto (image_prompt)
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

    schedule = _build_schedule(week_start)
    categories = CATEGORY_MIX[: len(schedule)]

    user_prompt = (
        f"Genereer {len(schedule)} sociale media posts voor de week van "
        f"{week_start.strftime('%d %B %Y')}.\n\n"
        f"Gebruik deze categorie-volgorde: {categories}\n\n"
        f"Geef je antwoord als een JSON-array met exact {len(schedule)} objecten, "
        f"elk met deze velden:\n"
        '- "category": één van: love, friends, travel, sports, parents, klusjes\n'
        '- "copy_nl": de volledige post tekst in het Nederlands (inclusief eventuele emojis)\n'
        '- "hashtags": string met hashtags, gescheiden door spaties (3-7 hashtags, mix NL/BE)\n'
        '- "image_prompt": Engelse beschrijving voor een lifestyle foto '
        '(warm, realistisch, 30+ mensen, Belgische setting)\n\n'
        'Geef ALLEEN de JSON array terug, geen andere tekst.'
    )

    logger.info("Generating %d posts for week %d/%d", len(schedule), week_number, year)

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
    for i, post in enumerate(posts_data[: len(schedule)]):
        result.append({
            **post,
            'scheduled_at': schedule[i],
            'week_number': week_number,
            'year': year,
        })

    logger.info("Generated %d posts successfully for week %d/%d", len(result), week_number, year)
    return result
