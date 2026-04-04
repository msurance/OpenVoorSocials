import logging
from pathlib import Path

from PIL import Image, ImageDraw
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

_BAR_COLOR = (26, 35, 58, int(255 * 0.85))

_LOGOBANNER_MAP = {
    'love': 'OpenVoorLiefde.jpg',
    'friends': 'OpenVoorVrienden.jpg',
    'travel': 'OpenVoorReizen.jpg',
    'sports': 'OpenVoorSporten.jpg',
    'parents': 'OpenVoorOuders.jpg',
}
_LOGOBANNER_FALLBACK = 'OpenVoorLiefde.jpg'


def _apply_branding(image_path: Path, category: str) -> None:
    """Overlay category-specific logobanner on a dark bar at the bottom of an image."""
    banner_name = _LOGOBANNER_MAP.get(category, _LOGOBANNER_FALLBACK)
    banner_path = Path(settings.BASE_DIR) / "logobanners" / banner_name

    if not banner_path.exists():
        logger.warning("Logobanner not found at %s — skipping branding overlay", banner_path)
        return

    img = Image.open(image_path).convert("RGBA")
    width, height = img.size

    bar_height = int(height * 0.13)
    bar_y = height - bar_height

    # Semi-transparent dark navy bar
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle([(0, bar_y), (width, height)], fill=_BAR_COLOR)
    img = Image.alpha_composite(img, overlay)

    # Scale logobanner to fit inside bar with vertical padding
    banner = Image.open(banner_path).convert("RGBA")
    pad = int(bar_height * 0.18)
    target_h = bar_height - 2 * pad
    aspect = banner.width / banner.height
    target_w = int(target_h * aspect)

    max_w = int(width * 0.75)
    if target_w > max_w:
        target_w = max_w
        target_h = int(target_w / aspect)

    banner_resized = banner.resize((target_w, target_h), Image.LANCZOS)

    # Center horizontally and vertically within bar
    x = (width - target_w) // 2
    y = bar_y + (bar_height - target_h) // 2

    img_rgb = img.convert("RGB")
    img_rgb.paste(banner_resized, (x, y))
    img_rgb.save(image_path, "PNG")


def generate_image(post_id: str, image_prompt: str, week_number: int, year: int, category: str = 'love') -> str:
    """
    Generate a square image via Gemini Imagen, apply category branding overlay, persist to MEDIA_ROOT.
    Returns the relative path within MEDIA_ROOT, e.g. 'posts/2026/14/uuid.png'.
    """
    client = genai.Client(api_key=settings.GOOGLE_API_KEY)

    full_prompt = f"{image_prompt}. {STYLE_SUFFIX}"

    logger.info("Generating image for post %s (category=%s)", post_id, category)

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

    _apply_branding(abs_path, category)
    logger.info("Image saved with branding: %s", abs_path)

    return relative_path
