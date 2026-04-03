import logging
from pathlib import Path

import google.generativeai as genai
from django.conf import settings

logger = logging.getLogger(__name__)

STYLE_SUFFIX = (
    "Warm lifestyle photography, realistic, natural lighting, "
    "teal and navy color accents, Belgian urban or nature setting, "
    "inclusive, adults aged 30-50, candid and authentic feel, "
    "no text overlays, no logos, high quality."
)


def generate_image(post_id: str, image_prompt: str, week_number: int, year: int) -> str:
    """
    Generate a square image via Gemini Imagen and persist it to MEDIA_ROOT.

    Returns the relative path within MEDIA_ROOT, e.g. 'posts/2026/14/uuid.png'.
    Raises on any API or I/O error (caller is responsible for logging/handling).
    """
    genai.configure(api_key=settings.GOOGLE_API_KEY)

    full_prompt = f"{image_prompt}. {STYLE_SUFFIX}"

    logger.info("Generating image for post %s", post_id)

    imagen = genai.ImageGenerationModel("imagen-3.0-generate-002")
    result = imagen.generate_images(
        prompt=full_prompt,
        number_of_images=1,
        aspect_ratio="1:1",
        safety_filter_level="block_some",
        person_generation="allow_adult",
    )

    # Persist to disk
    relative_dir = f"posts/{year}/{week_number}"
    abs_dir = Path(settings.MEDIA_ROOT) / relative_dir
    abs_dir.mkdir(parents=True, exist_ok=True)

    relative_path = f"{relative_dir}/{post_id}.png"
    abs_path = Path(settings.MEDIA_ROOT) / relative_path

    image_bytes = result.images[0]._image_bytes
    with open(abs_path, 'wb') as fh:
        fh.write(image_bytes)

    logger.info("Image saved to %s", abs_path)
    return relative_path
