import logging
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from google import genai
from google.genai import types
from django.conf import settings

logger = logging.getLogger(__name__)

STYLE_SUFFIX = (
    "Warm lifestyle photography, realistic, natural lighting, "
    "teal and navy color accents, Belgian urban or nature setting, "
    "inclusive, adults aged 30-50, candid and authentic feel, "
    "no text overlays, no logos, high quality."
)

# Branding overlay config
_LOGO_CROP = (20, 95, 115, 215)  # teardrop icon region in fb_banner_all.png
_BAR_COLOR = (26, 35, 58, int(255 * 0.82))
_BRAND_TEXT = "OpenVoor.app"


def _load_font(size):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "arial.ttf",
        "Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _apply_branding(image_path: Path) -> None:
    """Overlay the OpenVoor logo + domain on the bottom of an image."""
    banner_path = Path(settings.BASE_DIR) / "facebook_banners" / "fb_banner_all.png"
    if not banner_path.exists():
        logger.warning("Banner not found at %s — skipping branding overlay", banner_path)
        return

    banner = Image.open(banner_path).convert("RGBA")
    logo_rgba = banner.crop(_LOGO_CROP)

    img = Image.open(image_path).convert("RGBA")
    width, height = img.size

    bar_height = int(height * 0.12)
    bar_y = height - bar_height

    logo_target_h = int(bar_height * 0.65)
    logo_target_w = int(logo_target_h * logo_rgba.width / logo_rgba.height)
    logo_resized = logo_rgba.resize((logo_target_w, logo_target_h), Image.LANCZOS)

    pad_left = int(bar_height * 0.15)
    gap = int(bar_height * 0.12)
    font_size = int(bar_height * 0.38)
    font = _load_font(font_size)

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle([(0, bar_y), (width, height)], fill=_BAR_COLOR)
    img = Image.alpha_composite(img, overlay)

    logo_x = pad_left
    logo_y = bar_y + (bar_height - logo_target_h) // 2
    img.paste(logo_resized, (logo_x, logo_y), logo_resized)

    text_x = logo_x + logo_target_w + gap
    bbox = font.getbbox(_BRAND_TEXT)
    text_y = bar_y + (bar_height - (bbox[3] - bbox[1])) // 2 - bbox[1]
    ImageDraw.Draw(img).text((text_x, text_y), _BRAND_TEXT, font=font, fill=(255, 255, 255, 255))

    img.convert("RGB").save(image_path, "PNG")


def generate_image(post_id: str, image_prompt: str, week_number: int, year: int) -> str:
    """
    Generate a square image via Gemini Imagen, apply branding overlay, and persist to MEDIA_ROOT.
    Returns the relative path within MEDIA_ROOT, e.g. 'posts/2026/14/uuid.png'.
    """
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    full_prompt = f"{image_prompt}. {STYLE_SUFFIX}"

    logger.info("Generating image for post %s", post_id)

    result = client.models.generate_images(
        model="imagen-4.0-generate-001",
        prompt=full_prompt,
        config=types.GenerateImagesConfig(
            number_of_images=1,
            aspect_ratio="1:1",
            safety_filter_level="BLOCK_LOW_AND_ABOVE",
            person_generation="ALLOW_ADULT",
        ),
    )

    relative_dir = f"posts/{year}/{week_number}"
    abs_dir = Path(settings.MEDIA_ROOT) / relative_dir
    abs_dir.mkdir(parents=True, exist_ok=True)

    relative_path = f"{relative_dir}/{post_id}.png"
    abs_path = Path(settings.MEDIA_ROOT) / relative_path

    image_bytes = result.generated_images[0].image.image_bytes
    with open(abs_path, "wb") as fh:
        fh.write(image_bytes)

    _apply_branding(abs_path)
    logger.info("Image saved with branding: %s", abs_path)

    return relative_path
