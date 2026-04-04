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

_MOTION_PROMPTS = {
    'love': f'Soft warm glow, gentle bokeh drift, romantic cinematic stillness with subtle depth of field movement. {_STATIC_BANNER_INSTRUCTION}',
    'friends': f'Natural warmth, gentle ambient light flicker, subtle background movement, social energy. {_STATIC_BANNER_INSTRUCTION}',
    'travel': f'Scenic atmosphere, gentle camera drift, cinematic depth, natural light shift. {_STATIC_BANNER_INSTRUCTION}',
    'sports': f'Dynamic energy, subtle motion blur on edges, athletic atmosphere. {_STATIC_BANNER_INSTRUCTION}',
    'parents': f'Soft domestic warmth, gentle afternoon light shift, cozy peaceful movement. {_STATIC_BANNER_INSTRUCTION}',
}
_DEFAULT_MOTION = f'Gentle camera movement, soft ambient animation, cinematic warmth. {_STATIC_BANNER_INSTRUCTION}'


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

    motion_prompt = _MOTION_PROMPTS.get(category, _DEFAULT_MOTION)
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
