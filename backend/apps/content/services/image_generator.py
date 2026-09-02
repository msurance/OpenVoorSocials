import io
import logging
from pathlib import Path

from google import genai
from google.genai import types
from PIL import Image
from django.conf import settings

from apps.content.services.branding import apply_image_branding

logger = logging.getLogger(__name__)

# Google retired the standalone Imagen endpoint on this API tier (404 NOT_FOUND on
# imagen-4.0-generate-001 since 2026-08-29).  Gemini-native image generation is the
# replacement: generate_content with response_modalities=["IMAGE"].
# TODO: gemini-3.1-flash-image is ~cheaper if the weekly image bill matters more than fidelity.
IMAGE_MODEL = "gemini-3-pro-image"

STYLE_SUFFIX = (
    "Warm lifestyle photography, realistic, natural lighting, "
    "teal and navy color accents, Belgian urban or nature setting, "
    "inclusive, adults of various ages (18 to 75+), candid and authentic feel, "
    "no text overlays, no logos, high quality."
)


def _extract_image_bytes(result) -> bytes:
    """Pull the first inline image out of a generate_content response."""
    candidates = result.candidates or []
    for candidate in candidates:
        for part in (candidate.content.parts or []) if candidate.content else []:
            if part.inline_data and part.inline_data.data:
                return part.inline_data.data
    # No image: almost always a safety block or a text-only refusal — surface why.
    finish = candidates[0].finish_reason if candidates else 'no candidates'
    texts = [
        part.text
        for candidate in candidates
        for part in (candidate.content.parts or []) if candidate.content
        if part.text
    ]
    raise RuntimeError(f"{IMAGE_MODEL} returned no image (finish_reason={finish}): {' '.join(texts)[:200]}")


def generate_image(post_id: str, image_prompt: str, week_number: int, year: int, category: str = 'love') -> str:
    """
    Generate a 9:16 image via Gemini, apply category branding overlay, persist to MEDIA_ROOT.
    Also saves a raw (unbranded) backup as uuid_raw.png for clean Kling AI input.
    Returns the relative path within MEDIA_ROOT, e.g. 'posts/2026/14/uuid.png'.
    """
    client = genai.Client(
        api_key=settings.GOOGLE_API_KEY,
        http_options=types.HttpOptions(timeout=600_000),  # 600s — SDK uses ms
    )

    full_prompt = f"{image_prompt}. {STYLE_SUFFIX}"

    logger.info("Generating image for post %s (category=%s)", post_id, category)

    result = client.models.generate_content(
        model=IMAGE_MODEL,
        contents=full_prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            # 2K -> 1536x2752 raw, 1536x1920 after the 4:5 crop.  The 1K default
            # yields 768x960, below Instagram's 1080x1350 feed size.
            # person_generation is Vertex-only, so the old ALLOW_ADULT has no equivalent here.
            image_config=types.ImageConfig(aspect_ratio="9:16", image_size="2K"),
        ),
    )

    image_bytes = _extract_image_bytes(result)

    relative_dir = f"posts/{year}/{week_number}"
    abs_dir = Path(settings.MEDIA_ROOT) / relative_dir
    abs_dir.mkdir(parents=True, exist_ok=True)

    # Save raw backup — used by video generator for clean Kling AI input.
    # Gemini returns JPEG; re-encode to PNG so the .png the video step serves to
    # Kling really is a PNG (Django's static serve types it by extension).
    raw_path = abs_dir / f"{post_id}_raw.png"
    Image.open(io.BytesIO(image_bytes)).convert('RGB').save(raw_path, 'PNG')

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
