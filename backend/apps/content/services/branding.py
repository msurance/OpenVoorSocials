import json
import logging
import subprocess
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw
from django.conf import settings

logger = logging.getLogger(__name__)

_BAR_COLOR = (26, 35, 58, int(255 * 0.85))

_LOGOBANNER_MAP = {
    'love': 'OpenVoorLiefde.jpg',
    'friends': 'OpenVoorVrienden.jpg',
    'travel': 'OpenVoorReizen.jpg',
    'sports': 'OpenVoorSporten.jpg',
    'parents': 'OpenVoorOuders.jpg',
}
_LOGOBANNER_FALLBACK = 'OpenVoorLiefde.jpg'


def _banner_path(category: str) -> Path:
    name = _LOGOBANNER_MAP.get(category, _LOGOBANNER_FALLBACK)
    return Path(settings.BASE_DIR) / 'logobanners' / name


def _create_overlay_png(dest: Path, width: int, height: int, category: str) -> None:
    """Create a transparent PNG with the dark bar + logo at the bottom, sized width x height."""
    banner_src = _banner_path(category)
    if not banner_src.exists():
        logger.warning("Logobanner not found: %s", banner_src)
        return

    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))

    bar_height = int(height * 0.13)
    bar_y = height - bar_height

    ImageDraw.Draw(overlay).rectangle([(0, bar_y), (width, height)], fill=_BAR_COLOR)

    banner = Image.open(banner_src).convert('RGBA')
    pad = int(bar_height * 0.18)
    target_h = bar_height - 2 * pad
    aspect = banner.width / banner.height
    target_w = int(target_h * aspect)
    max_w = int(width * 0.75)
    if target_w > max_w:
        target_w = max_w
        target_h = int(target_w / aspect)

    banner_resized = banner.resize((target_w, target_h), Image.LANCZOS)
    x = (width - target_w) // 2
    y = bar_y + (bar_height - target_h) // 2
    overlay.paste(banner_resized, (x, y), banner_resized)

    overlay.save(dest, 'PNG')


def apply_image_branding(image_path: Path, category: str) -> None:
    """Overlay category logobanner on a dark bar at the bottom of an image (in-place)."""
    banner_src = _banner_path(category)
    if not banner_src.exists():
        logger.warning("Logobanner not found at %s — skipping branding", banner_src)
        return

    img = Image.open(image_path).convert('RGBA')
    width, height = img.size

    bar_height = int(height * 0.13)
    bar_y = height - bar_height

    overlay = Image.new('RGBA', img.size, (0, 0, 0, 0))
    ImageDraw.Draw(overlay).rectangle([(0, bar_y), (width, height)], fill=_BAR_COLOR)
    img = Image.alpha_composite(img, overlay)

    banner = Image.open(banner_src).convert('RGBA')
    pad = int(bar_height * 0.18)
    target_h = bar_height - 2 * pad
    aspect = banner.width / banner.height
    target_w = int(target_h * aspect)
    max_w = int(width * 0.75)
    if target_w > max_w:
        target_w = max_w
        target_h = int(target_w / aspect)

    banner_resized = banner.resize((target_w, target_h), Image.LANCZOS)
    x = (width - target_w) // 2
    y = bar_y + (bar_height - target_h) // 2

    img_rgb = img.convert('RGB')
    img_rgb.paste(banner_resized, (x, y), banner_resized)
    img_rgb.save(image_path, 'PNG')


def apply_video_branding(video_path: Path, category: str) -> None:
    """
    Overlay category logobanner on a dark bar at the bottom of a video (in-place).
    Requires ffmpeg + ffprobe to be installed. Logs and returns without error if not available.
    """
    banner_src = _banner_path(category)
    if not banner_src.exists():
        logger.warning("Logobanner not found — skipping video branding")
        return

    # Get video dimensions via ffprobe
    try:
        probe = subprocess.run(
            ['ffprobe', '-v', 'quiet', '-print_format', 'json', '-show_streams', str(video_path)],
            capture_output=True, text=True, timeout=15,
        )
    except FileNotFoundError:
        logger.warning("ffprobe not found — skipping video branding for %s", video_path)
        return
    except subprocess.TimeoutExpired:
        logger.error("ffprobe timed out for %s — skipping video branding", video_path)
        return

    if probe.returncode != 0:
        logger.error("ffprobe failed for %s: %s", video_path, probe.stderr)
        return

    streams = json.loads(probe.stdout).get('streams', [])
    video_stream = next((s for s in streams if s.get('codec_type') == 'video'), None)
    if not video_stream:
        logger.error("No video stream found in %s", video_path)
        return

    width = int(video_stream['width'])
    height = int(video_stream['height'])
    logger.info("Video dimensions: %dx%d", width, height)

    # Create overlay PNG in a temp file
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_overlay:
        overlay_path = Path(tmp_overlay.name)

    try:
        _create_overlay_png(overlay_path, width, height, category)

        tmp_output = video_path.with_suffix('.branded.mp4')
        try:
            result = subprocess.run(
                [
                    'ffmpeg', '-y',
                    '-i', str(video_path),
                    '-i', str(overlay_path),
                    '-filter_complex', '[0:v][1:v]overlay=0:0',
                    '-c:v', 'libx264',
                    '-preset', 'fast',
                    '-crf', '23',
                    '-c:a', 'copy',
                    str(tmp_output),
                ],
                capture_output=True, text=True, timeout=120,
            )
        except FileNotFoundError:
            logger.warning("ffmpeg not found — skipping video branding for %s", video_path)
            return
        except subprocess.TimeoutExpired:
            logger.error("ffmpeg timed out for %s — skipping video branding", video_path)
            tmp_output.unlink(missing_ok=True)
            return

        if result.returncode != 0:
            logger.error("ffmpeg branding failed for %s: %s", video_path, result.stderr[-500:])
            tmp_output.unlink(missing_ok=True)
            return

        tmp_output.rename(video_path)
        logger.info("Video branding applied: %s", video_path)

    finally:
        overlay_path.unlink(missing_ok=True)
