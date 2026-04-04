import logging
import time
import requests
from pathlib import Path

from django.conf import settings

logger = logging.getLogger(__name__)

_FAL_ENDPOINT = "https://queue.fal.run/fal-ai/kling-video/v1.6/standard/image-to-video"

_STATIC_BANNER_INSTRUCTION = (
    "The dark navy bar at the very bottom of the frame with the brand logo and text "
    "is a static UI overlay — keep it completely sharp, fully visible, and unchanged "
    "throughout the entire video. Do not animate, fade, blur, or distort it."
)

# Multiple motion styles per category — rotated by post_id hash so the same
# post always gets the same style, but different posts vary naturally.
_MOTION_PROMPTS = {
    'love': [
        f'Gentle bokeh drift, soft warm light slowly brightening, romantic depth-of-field pulse, stillness with heartbeat energy. {_STATIC_BANNER_INSTRUCTION}',
        f'Slow cinematic push-in, golden hour glow intensifying, subtle lens flare drift across the frame. {_STATIC_BANNER_INSTRUCTION}',
        f'Soft parallax between subject and background, warm candlelight flicker, intimate and unhurried. {_STATIC_BANNER_INSTRUCTION}',
    ],
    'friends': [
        f'Light ambient movement in the background, natural laugh-energy ripple, warm social atmosphere. {_STATIC_BANNER_INSTRUCTION}',
        f'Gentle handheld sway, café background buzz, spontaneous candid energy, bright mid-afternoon light. {_STATIC_BANNER_INSTRUCTION}',
        f'Subtle zoom-out revealing more of the scene, background crowd softly animating, upbeat warmth. {_STATIC_BANNER_INSTRUCTION}',
    ],
    'travel': [
        f'Slow cinematic pan revealing the landscape, golden light shifting across the scene, sense of arrival. {_STATIC_BANNER_INSTRUCTION}',
        f'Gentle camera drift forward as if walking into the scene, atmospheric haze, wanderlust energy. {_STATIC_BANNER_INSTRUCTION}',
        f'Parallax depth pull between foreground and horizon, natural wind movement, epic stillness. {_STATIC_BANNER_INSTRUCTION}',
    ],
    'sports': [
        f'Subtle dynamic energy pulse, motion blur ripple on background, athletic readiness, focused tension. {_STATIC_BANNER_INSTRUCTION}',
        f'Slow zoom in on the subject, environment softly energising around them, momentum building. {_STATIC_BANNER_INSTRUCTION}',
        f'Gentle camera tilt with depth shimmer, crisp morning light, outdoor freshness, movement potential. {_STATIC_BANNER_INSTRUCTION}',
    ],
    'parents': [
        f'Soft afternoon light slowly shifting, cozy domestic warmth, quiet tenderness, unhurried pace. {_STATIC_BANNER_INSTRUCTION}',
        f'Gentle parallax between subject and family-life background details, safe and warm atmosphere. {_STATIC_BANNER_INSTRUCTION}',
        f'Slow subtle push-in, window light brightening, peaceful kitchen or living room energy. {_STATIC_BANNER_INSTRUCTION}',
    ],
}
_DEFAULT_PROMPTS = [
    f'Gentle camera movement, soft ambient animation, cinematic warmth. {_STATIC_BANNER_INSTRUCTION}',
    f'Slow atmospheric drift, natural light shift, serene and engaging. {_STATIC_BANNER_INSTRUCTION}',
]


def _pick_motion_prompt(category: str, post_id: str) -> str:
    """Deterministically pick a motion prompt variant based on post_id."""
    options = _MOTION_PROMPTS.get(category, _DEFAULT_PROMPTS)
    index = int(post_id.replace('-', '')[:8], 16) % len(options)
    return options[index]


def _fal_headers():
    return {
        "Authorization": f"Key {settings.FAL_KEY}",
        "Content-Type": "application/json",
    }


def generate_video(post_id: str, image_path_relative: str, category: str, week_number: int, year: int) -> str:
    """
    Generate a 5-second video from the post image using Kling AI via fal.ai REST API.
    Uses the queue endpoint with polling — no fal_client SDK (avoids auto-upload 403).
    Returns relative path within MEDIA_ROOT, e.g. 'posts/2026/15/uuid.mp4'.
    """
    abs_image_path = Path(settings.MEDIA_ROOT) / image_path_relative
    if not abs_image_path.exists():
        raise FileNotFoundError(f"Image not found: {abs_image_path}")

    motion_prompt = _pick_motion_prompt(category, post_id)
    image_url = f"{settings.BASE_URL}{settings.MEDIA_URL}{image_path_relative}"

    logger.info("Submitting video job for post %s (image=%s)", post_id, image_url)

    # Step 1: Submit to queue
    resp = requests.post(
        _FAL_ENDPOINT,
        headers=_fal_headers(),
        json={
            "prompt": motion_prompt,
            "image_url": image_url,
            "duration": "5",
            "aspect_ratio": "1:1",
        },
        timeout=30,
    )
    resp.raise_for_status()
    job = resp.json()
    request_id = job["request_id"]
    status_url = job["status_url"]
    response_url = job["response_url"]
    logger.info("Video job queued: request_id=%s", request_id)

    # Step 2: Poll until complete (max 5 minutes)
    for attempt in range(60):
        time.sleep(5)
        status_resp = requests.get(status_url, headers=_fal_headers(), timeout=15)
        status_resp.raise_for_status()
        status = status_resp.json().get("status")
        logger.info("Video job %s status: %s (attempt %d)", request_id, status, attempt + 1)
        if status == "COMPLETED":
            break
        if status in ("FAILED", "CANCELLED"):
            raise RuntimeError(f"fal.ai video job {request_id} ended with status: {status}")
    else:
        raise TimeoutError(f"fal.ai video job {request_id} did not complete within 5 minutes")

    # Step 3: Fetch result
    result_resp = requests.get(response_url, headers=_fal_headers(), timeout=15)
    result_resp.raise_for_status()
    result = result_resp.json()
    video_download_url = result["video"]["url"]

    # Step 4: Download and save
    relative_dir = f"posts/{year}/{week_number}"
    abs_dir = Path(settings.MEDIA_ROOT) / relative_dir
    abs_dir.mkdir(parents=True, exist_ok=True)

    relative_path = f"{relative_dir}/{post_id}.mp4"
    abs_path = Path(settings.MEDIA_ROOT) / relative_path

    logger.info("Downloading video for post %s from %s", post_id, video_download_url)
    dl = requests.get(video_download_url, timeout=120)
    dl.raise_for_status()
    with open(abs_path, "wb") as f:
        f.write(dl.content)

    logger.info("Video saved: %s", abs_path)
    return relative_path
