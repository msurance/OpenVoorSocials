import logging
import os
import requests
from pathlib import Path

import fal_client
from django.conf import settings

logger = logging.getLogger(__name__)

_STATIC_BANNER_INSTRUCTION = (
    "The dark navy bar at the very bottom of the frame with the brand logo and text "
    "is a static UI overlay — keep it completely sharp, fully visible, and unchanged "
    "throughout the entire video. Do not animate, fade, blur, or distort it."
)

_MOTION_PROMPTS = {
    'love': f'Soft warm glow, gentle bokeh drift, romantic cinematic stillness with subtle depth of field movement. {_STATIC_BANNER_INSTRUCTION}',
    'friends': f'Natural warmth, gentle ambient light flicker, subtle background movement, social energy. {_STATIC_BANNER_INSTRUCTION}',
    'travel': f'Scenic atmosphere, gentle camera drift, cinematic depth, natural light shift. {_STATIC_BANNER_INSTRUCTION}',
    'sports': f'Dynamic energy, subtle motion blur on edges, athletic atmosphere. {_STATIC_BANNER_INSTRUCTION}',
    'parents': f'Soft domestic warmth, gentle afternoon light shift, cozy peaceful movement. {_STATIC_BANNER_INSTRUCTION}',
}
_DEFAULT_MOTION = f'Gentle camera movement, soft ambient animation, cinematic warmth. {_STATIC_BANNER_INSTRUCTION}'


def generate_video(post_id: str, image_path_relative: str, category: str, week_number: int, year: int) -> str:
    """
    Generate a 5-second video from the post image using Kling AI via fal.ai.
    Returns relative path within MEDIA_ROOT, e.g. 'posts/2026/15/uuid.mp4'.
    """
    abs_image_path = Path(settings.MEDIA_ROOT) / image_path_relative
    if not abs_image_path.exists():
        raise FileNotFoundError(f"Image not found: {abs_image_path}")

    os.environ['FAL_KEY'] = settings.FAL_KEY

    motion_prompt = _MOTION_PROMPTS.get(category, _DEFAULT_MOTION)

    # Use the public URL directly — avoids fal.ai CDN storage upload permissions
    image_url = f"{settings.BASE_URL}{settings.MEDIA_URL}{image_path_relative}"

    logger.info("Generating video for post %s (category=%s, image=%s)", post_id, category, image_url)
    result = fal_client.run(
        "fal-ai/kling-video/v1.6/standard/image-to-video",
        arguments={
            "prompt": motion_prompt,
            "image_url": image_url,
            "duration": "5",
            "aspect_ratio": "1:1",
        },
    )

    video_download_url = result["video"]["url"]

    relative_dir = f"posts/{year}/{week_number}"
    abs_dir = Path(settings.MEDIA_ROOT) / relative_dir
    abs_dir.mkdir(parents=True, exist_ok=True)

    relative_path = f"{relative_dir}/{post_id}.mp4"
    abs_path = Path(settings.MEDIA_ROOT) / relative_path

    logger.info("Downloading video for post %s", post_id)
    response = requests.get(video_download_url, timeout=120)
    response.raise_for_status()
    with open(abs_path, 'wb') as f:
        f.write(response.content)

    logger.info("Video saved: %s", abs_path)
    return relative_path
