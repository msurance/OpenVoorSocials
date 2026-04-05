import logging
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image
from django.conf import settings

from apps.content.services.branding import apply_image_branding

logger = logging.getLogger(__name__)

STYLE_SUFFIX = (
    "Warm lifestyle photography, realistic, natural lighting, "
    "teal and navy color accents, Belgian urban or nature setting, "
    "inclusive, adults of various ages (18+), candid and authentic feel, "
    "no text overlays, no logos, high quality."
)


def generate_image(post_id: str, image_prompt: str, week_number: int, year: int, category: str = 'love') -> str:
    """
    Generate a square image via Gemini Imagen, apply category branding overlay, persist to MEDIA_ROOT.
    Also saves a raw (unbranded) backup as uuid_raw.png for clean Kling AI input.
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
            aspect_ratio="9:16",
            safety_filter_level="BLOCK_LOW_AND_ABOVE",
            person_generation="ALLOW_ADULT",
        ),
    )

    relative_dir = f"posts/{year}/{week_number}"
    abs_dir = Path(settings.MEDIA_ROOT) / relative_dir
    abs_dir.mkdir(parents=True, exist_ok=True)

    image_bytes = result.generated_images[0].image.image_bytes

    # Save raw backup — used by video generator for clean Kling AI input
    raw_path = abs_dir / f"{post_id}_raw.png"
    with open(raw_path, 'wb') as fh:
        fh.write(image_bytes)

    # Center-crop 9:16 raw image to 4:5 for the static feed post
    raw_img = Image.open(raw_path)
    raw_w, raw_h = raw_img.size
    target_h = int(raw_w * 5 / 4)
    if target_h > raw_h:
        # Image shorter than 4:5 (unexpected) — crop width instead
        target_h = raw_h
        target_w = int(raw_h * 4 / 5)
        left = (raw_w - target_w) // 2
        cropped = raw_img.crop((left, 0, left + target_w, raw_h))
    else:
        top = (raw_h - target_h) // 2
        cropped = raw_img.crop((0, top, raw_w, top + target_h))

    relative_path = f"{relative_dir}/{post_id}.png"
    abs_path = Path(settings.MEDIA_ROOT) / relative_path
    cropped.save(abs_path, 'PNG')

    apply_image_branding(abs_path, category)
    logger.info("Image saved with branding (4:5 crop of 9:16 source): %s", abs_path)

    return relative_path
