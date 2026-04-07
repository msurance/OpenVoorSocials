import json
import logging
import random
from datetime import datetime, timedelta

import anthropic
from django.conf import settings
from django.utils.timezone import make_aware

logger = logging.getLogger(__name__)

# Per-category instructions for the "expert matching" angle:
# References the well-known TV genre (Blind Getrouwd, Love is Blind, Married at First Sight…)
# without naming any specific show — avoids trademark issues while keeping full recognisability.
BLIND_GETROUWD_ANGLES = {
    'love': (
        "Schrijf deze post vanuit het concept van tv-programma's waar een expertengroep mensen blind matcht op basis van "
        "persoonlijkheid, waarden en levensvisie — niet op uiterlijk. Je ziet elkaar pas nadat de experts beslist hebben "
        "dat jullie op papier bij elkaar passen. Bij OpenVoor is de AI-Expertengroep die expertengroep. "
        "Verwijs naar het herkenbare genre zonder een specifieke show te noemen: 'zoals in die programma's waar experts "
        "voor jou kiezen', 'blind gematcht op wie je écht bent', 'de AI-Expertengroep beslist — niet jouw foto'. "
        "Toon: luchtig, herkenbaar, een tikje spannend."
    ),
    'friends': (
        "Schrijf deze post vanuit het concept van tv-programma's waar experts mensen blind koppelen op compatibiliteit "
        "— maar dan voor vriendschap. De AI-Expertengroep van OpenVoor koppelt jou aan iemand die écht bij je past "
        "als vriend: zelfde humor, zelfde tempo, zelfde interesses. Geen profielfoto's scrollen. "
        "Verwijs naar het herkenbare genre zonder een specifieke show te noemen: 'zoals die programma's waar een "
        "expertengroep voor jou kiest', 'blind gematcht op vriendschap'. "
        "Toon: warm, herkenbaar, lichtjes grappig over hoe awkward vrienden maken als volwassene is."
    ),
    'travel': (
        "Schrijf deze post vanuit het concept van tv-programma's waar experts mensen blind matchen — maar dan voor "
        "reisgenoten. De AI-Expertengroep koppelt jou aan de perfecte reisgezel op basis van hoe jij reist: tempo, "
        "budget, avontuurlijkheid. Verwijs naar het herkenbare genre zonder een specifieke show te noemen: "
        "'zoals die programma's waar een expertengroep beslist wie bij wie past', 'blind op reis met iemand die "
        "perfect op papier matcht'. Toon: avontuurlijk, nieuwsgierig, een tikje humoristisch."
    ),
    'sports': (
        "Schrijf deze post vanuit het concept van tv-programma's waar experts mensen blind koppelen op compatibiliteit "
        "— maar dan voor sportmaatjes. De AI-Expertengroep matcht jou aan iemand met hetzelfde sportniveau, dezelfde "
        "motivatie en hetzelfde tijdsschema. Verwijs naar het herkenbare genre zonder een specifieke show te noemen: "
        "'zoals die programma's waar een expertengroep voor jou kiest', 'blind gematcht op sportritme'. "
        "Toon: energiek, motiverend, herkenbaar."
    ),
    'parents': (
        "Schrijf deze post vanuit het concept van tv-programma's waar experts mensen blind matchen op basis van wie ze "
        "écht zijn — maar dan voor ouders. De AI-Expertengroep koppelt jou aan een andere ouder waarvan de kinderen in "
        "exact dezelfde levensfase zitten. Geen romantiek — gewoon iemand die begrijpt hoe jij het aanpakt. "
        "Verwijs naar het herkenbare genre zonder een specifieke show te noemen: 'zoals die programma's waar een "
        "expertengroep matcht op papier, maar dan voor ouders', 'blind gematcht op levensfase'. "
        "Toon: herkenbaar, warm, luchtig."
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

# Three publishing slots per day — gives 21 slots per week (enough headroom for any count)
POST_TIMES = ['10:00', '13:00', '19:00']

SYSTEM_PROMPT = """Je bent een sociale media expert voor OpenVoor.app, een Belgisch AI-matchmaking platform voor volwassenen (18+).
OpenVoor.app helpt mensen die moeite hebben om nieuwe verbindingen te vinden — voor liefde, vriendschap, sport, reizen en ouderschap.

BELANGRIJK voor de categorie 'parents': dit gaat NIET over daten of een romantische partner zoeken voor mensen met kinderen. Het gaat over ouders verbinden met andere ouders waarvan de kinderen in dezelfde levensfase zitten — zelfde leeftijd, zelfde uitdagingen, zelfde vragen. Zodat ze ervaringen kunnen uitwisselen, samen activiteiten kunnen doen met de kinderen, of gewoon iemand hebben die begrijpt hoe het voelt. Denk aan: een wandeling met de buggy's, samen naar het park, ervaringen delen over slaapproblemen of schoolkeuze. Nooit romantisch.

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
- Voor de categorie 'parents': toon twee of meer volwassenen (de ouders) samen in een gezinscontext — wandelen met een buggy, op een speelplein, in een park. Kinderen mogen zichtbaar zijn maar zijn nooit het hoofdonderwerp. De verbinding tussen de ouders staat centraal.
- De foto moet realistisch en authentiek aanvoelen, Belgische setting.
"""


def _build_schedule(week_start: datetime) -> list[datetime]:
    """
    Return up to 21 scheduled datetime objects for the week.

    Strategy: three posts per day (10:00 + 13:00 + 19:00) across all 7 days
    starting Tuesday, giving exactly 21 slots.  The [:21] cap is a safety guard only.
    """
    schedule = []
    for day_offset in range(1, 8):  # Tuesday through Monday (7 days)
        day = week_start + timedelta(days=day_offset)
        for t in POST_TIMES:
            h, m = map(int, t.split(':'))
            naive_dt = day.replace(hour=h, minute=m, second=0, microsecond=0, tzinfo=None)
            schedule.append(make_aware(naive_dt))
    return schedule[:21]


def generate_weekly_posts(week_number: int, year: int, count: int = None, categories: list = None) -> list[dict]:
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

    # Build the pool: use provided categories or fall back to CATEGORY_MIX
    if categories:
        base = categories
    else:
        base = CATEGORY_MIX.copy()

    # Cycle the base pool to meet the requested count (or default to len(base))
    target = count if count else len(base)
    pool = [base[i % len(base)] for i in range(max(target, len(base)))]
    random.shuffle(pool)
    n = min(target, len(pool))
    categories = pool[:n]
    schedule = _build_schedule(week_start)[:n]

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
