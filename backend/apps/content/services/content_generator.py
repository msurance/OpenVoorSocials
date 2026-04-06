import json
import logging
import random
from datetime import datetime, timedelta

import anthropic
from django.conf import settings

logger = logging.getLogger(__name__)

# Per-category instructions for the "Blind Getrouwd" angle:
# OpenVoor = the AI expert group that matches you on paper (anonymised data),
# just like the show's experts — but across all life domains.
BLIND_GETROUWD_ANGLES = {
    'love': (
        "Schrijf deze post vanuit het 'Blind Getrouwd'-perspectief: in die show beslissen experts wie bij wie past. "
        "Bij OpenVoor.app doet AI dat — volledig op basis van wie je écht bent, zonder foto's of oppervlakkig swipen. "
        "Verwijs speels naar het concept: 'onze expertengroep bestaat uit AI', 'op papier gematcht voordat je elkaar ziet', "
        "'net als Blind Getrouwd maar dan zonder camera'. Houd de toon luchtig en herkenbaar."
    ),
    'friends': (
        "Schrijf deze post vanuit het 'Blind Getrouwd voor vriendschappen'-perspectief: wat als een AI-expertengroep "
        "jou koppelt aan iemand die écht bij je past als vriend — op basis van gedeelde interesses, waarden en ritme? "
        "Verwijs naar het idee van 'gematcht op papier' maar dan voor vriendschap. "
        "Toon: herkenbaar, warm, lichtjes grappig over hoe moeilijk vrienden maken als volwassene is."
    ),
    'travel': (
        "Schrijf deze post vanuit het 'Blind Getrouwd voor reisgenoten'-perspectief: een AI-expertengroep matcht jou "
        "met de perfecte reiscompanion op basis van reisritme, budget, interesses — niet op uiterlijk. "
        "Verwijs naar het idee van 'blind op reis gaan met iemand die de experts voor jou kozen'. "
        "Toon: avontuurlijk, nieuwsgierig, een tikje humoristisch."
    ),
    'sports': (
        "Schrijf deze post vanuit het 'Blind Getrouwd voor sportmaatjes'-perspectief: de AI-expertengroep koppelt "
        "jou aan iemand met hetzelfde sportniveau, dezelfde motivatie en hetzelfde tijdsschema. "
        "Verwijs naar 'gematcht op papier' maar dan voor de sportclub of het wandelpad. "
        "Toon: energiek, motiverend, herkenbaar voor wie moeite heeft een sportmaatje te vinden."
    ),
    'parents': (
        "Schrijf deze post vanuit het 'Blind Getrouwd voor ouders'-perspectief: de AI-expertengroep matcht ouders "
        "met andere ouders in dezelfde levensfase — zelfde leeftijd kinderen, zelfde uitdagingen, zelfde waarden. "
        "Verwijs naar 'op papier gematcht met een andere ouder die écht begrijpt hoe jij het aanpakt'. "
        "Toon: herkenbaar, warm, een beetje self-aware over de chaos van het ouderschap."
    ),
}

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

# Two optimal publishing slots
POST_TIMES = ['10:00', '19:00']

SYSTEM_PROMPT = """Je bent een sociale media expert voor OpenVoor.app, een Belgisch AI-matchmaking platform voor volwassenen (18+).
OpenVoor.app helpt mensen die moeite hebben om nieuwe verbindingen te vinden — voor liefde, vriendschap, sport, reizen en ouderschap.

Schrijf authentieke, warme en herkenbare Nederlandse posts voor Facebook en Instagram.
Doelgroep: Belgen van alle leeftijden (minimum 18 jaar). De realiteit is dat eenzaamheid en de zoektocht naar verbinding mensen van 25 tot 75 treft. Verdeel de posts over de volledige leeftijdsspectrum — twintigers, dertigers, veertigers, vijftigers, en ook mensen in de 60 en 70. Sommige posts mogen een specifieke leeftijdsgroep aanspreken, maar doe dit enkel als het organisch past bij het thema.
Toon: warm, eerlijk, niet te commercieel, lichtjes humoristisch waar gepast.
NIET: geen technologisch jargon, geen "algoritme"-taal, geen generieke dating-app clichés. Vermijd generieke leeftijdsverwijzingen tenzij het thema daar specifiek om vraagt.

Elke post moet:
1. Beginnen met een herkenbare situatie of vraag (geen app-reclame als opener)
2. Het opgegeven OpenVoor-kenmerk (tagline) organisch verwerken in de post — niet als los zinnetje eraan plakken, maar als iets dat vanzelfsprekend past in de context
3. Eindigen met een zachte call-to-action richting OpenVoor.app
4. 3-7 relevante Belgische/Nederlandse hashtags bevatten
5. Een concrete, levendige beschrijving bevatten voor een lifestyle foto (image_prompt)

Belangrijk voor image_prompt:
- De image_prompt MOET de concrete situatie uit copy_nl weerspiegelen. Als de post over fietsen gaat → mensen op de fiets. Over koken → mensen in de keuken. Over wandelen → mensen op een pad. Kopieer NOOIT het beeld van een andere post.
- Beschrijf de exacte activiteit, locatie en sfeer die in de post centraal staat — wees specifiek, niet generiek.
- Varieer de setting sterk tussen posts: café, park, bos, stadsplein, strand, markt, sportclub, woonkamer, terras, museum, bibliotheek, etc.
- Beschrijf ALLEEN volwassenen (minimum 18 jaar) — geen kinderen, geen baby's.
- Varieer de leeftijd actief: ook regelmatig mensen van 60-75 jaar. Gebruik NIET standaard jonge mensen.
- Voor de categorie 'parents': toon de ouder via rekwisieten en omgeving (speelgoed, kindertekeningen, kleine laarsjes) maar GEEN kinderen zichtbaar in het beeld.
- De foto moet realistisch en authentiek aanvoelen, Belgische setting.
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
    from apps.params.helpers import get_param

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    # Determine Monday of the requested ISO week
    # ISO week 1 contains the first Thursday of the year; Jan 4 is always in week 1.
    jan4 = datetime(year, 1, 4)
    week_start = jan4 + timedelta(weeks=week_number - 1, days=-jan4.weekday())

    schedule = _build_schedule(week_start)[:len(CATEGORY_MIX)]
    categories = CATEGORY_MIX.copy()
    random.shuffle(categories)

    # Determine which posts get the "Blind Getrouwd" AI-expert angle
    n_bg = get_param('content.blind_getrouwd_per_week', 4)
    bg_indices = set(random.sample(range(len(categories)), min(n_bg, len(categories))))

    # Assign one rotating tagline per post, plus optional BG angle
    tagged = [
        (categories[i], TAGLINES[i % len(TAGLINES)])
        for i in range(len(categories))
    ]
    post_specs_lines = []
    for i, (cat, tag) in enumerate(tagged):
        line = f"{i+1}. categorie: {cat} | tagline om te verwerken: \"{tag}\""
        if i in bg_indices:
            angle = BLIND_GETROUWD_ANGLES.get(cat, '')
            line += f" | BLIND GETROUWD HOEK: {angle}"
        post_specs_lines.append(line)
    post_specs = "\n".join(post_specs_lines)

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
        '- "image_prompt": Engelse beschrijving voor een lifestyle foto die DIRECT aansluit bij de '
        'specifieke situatie in copy_nl (zelfde activiteit, zelfde setting). '
        'Elke image_prompt moet een unieke locatie en activiteit beschrijven — geen twee posts met hetzelfde beeld. '
        'Wees concreet: beschrijf wat mensen doen, waar ze zijn, wat er in de achtergrond staat.\n\n'
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

    # Pick N posts to receive a discount CTA
    from apps.content.services.cta_generator import generate_cta
    n_cta = get_param('engagement.discount_cta_per_week', 3)
    cta_indices = set(random.sample(range(len(posts_data)), min(n_cta, len(posts_data))))

    # Pick one of the engagement keywords to use as the CTA keyword
    kw_str = get_param('engagement.keywords', 'match,openvoor,klaar,korting')
    keywords = [k.strip() for k in kw_str.split(',') if k.strip()]

    result = []
    for i, post in enumerate(posts_data[:len(categories)]):
        has_cta = i in cta_indices
        copy_nl = post['copy_nl']
        if has_cta:
            # Rotate through keywords deterministically by index
            keyword = keywords[i % len(keywords)].upper()
            cta = generate_cta(category=post['category'], copy_nl=copy_nl, keyword=keyword)
            copy_nl = f"{copy_nl}\n\n{cta}"
            logger.info("CTA added to post %d (category=%s, keyword=%s)", i + 1, post['category'], keyword)
        result.append({
            **post,
            'copy_nl': copy_nl,
            'discount_cta': has_cta,
            'scheduled_at': schedule[i],
            'week_number': week_number,
            'year': year,
        })

    logger.info("Generated %d posts successfully for week %d/%d", len(result), week_number, year)

    return result
