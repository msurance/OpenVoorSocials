"""
Apply OpenVoor.app branding overlay to social media images.
Adds a semi-transparent dark navy bar at the bottom with logo + text.
"""

import os
import glob
from PIL import Image, ImageDraw, ImageFont

# --- Paths ---
BANNER_PATH = "C:/ClaudeProjects/OpenVoorSocials/facebook_banners/fb_banner_all.png"
IMAGES_DIR = "C:/ClaudeProjects/OpenVoorSocials/backend/media/posts/2026/15/"
BRAND_TEXT = "OpenVoor.app"

# --- Logo crop region from banner (820x312) ---
LOGO_CROP = (20, 95, 115, 215)  # (left, top, right, bottom)

# --- Bar style ---
BAR_COLOR = (26, 35, 58, int(255 * 0.82))  # rgba dark navy


def load_font(size):
    """Try system fonts in order, fall back to default."""
    candidates = [
        "arial.ttf",
        "Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except (IOError, OSError):
            continue
    # Last resort: built-in default with size hint
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def extract_logo(banner_path, crop_box):
    """Crop the teardrop logo from the banner and return as RGBA image."""
    banner = Image.open(banner_path).convert("RGBA")
    logo = banner.crop(crop_box)
    return logo


def apply_branding(image_path, logo_rgba):
    """Apply branding overlay to a single image and overwrite it."""
    img = Image.open(image_path).convert("RGBA")
    width, height = img.size

    # --- Bar dimensions ---
    bar_height = int(height * 0.12)
    bar_y = height - bar_height

    # --- Scale logo to fit bar ---
    logo_target_h = int(bar_height * 0.65)
    logo_aspect = logo_rgba.width / logo_rgba.height
    logo_target_w = int(logo_target_h * logo_aspect)
    logo_resized = logo_rgba.resize(
        (logo_target_w, logo_target_h), Image.LANCZOS
    )

    # --- Layout padding / gap ---
    pad_left = int(bar_height * 0.15)
    gap = int(bar_height * 0.12)
    font_size = int(bar_height * 0.38)
    font = load_font(font_size)

    # --- Draw bar overlay onto a transparent layer ---
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    draw.rectangle(
        [(0, bar_y), (width, height)],
        fill=BAR_COLOR,
    )

    # --- Composite bar onto image ---
    img = Image.alpha_composite(img, overlay)

    # --- Paste logo (vertically centered in bar) ---
    logo_y = bar_y + (bar_height - logo_target_h) // 2
    logo_x = pad_left
    img.paste(logo_resized, (logo_x, logo_y), logo_resized)

    # --- Draw text ---
    text_x = logo_x + logo_target_w + gap
    # Measure text height for vertical centering
    bbox = font.getbbox(BRAND_TEXT)
    text_h = bbox[3] - bbox[1]
    text_y = bar_y + (bar_height - text_h) // 2 - bbox[1]

    draw2 = ImageDraw.Draw(img)
    draw2.text(
        (text_x, text_y),
        BRAND_TEXT,
        font=font,
        fill=(255, 255, 255, 255),
    )

    # --- Save back as PNG (convert to RGB to drop alpha for final output) ---
    final = img.convert("RGB")
    final.save(image_path, "PNG")
    return True


def main():
    logo = extract_logo(BANNER_PATH, LOGO_CROP)

    pattern = os.path.join(IMAGES_DIR, "*.png")
    files = sorted(glob.glob(pattern))

    if not files:
        print(f"No PNG files found in {IMAGES_DIR}")
        return

    print(f"Processing {len(files)} images...\n")
    for path in files:
        filename = os.path.basename(path)
        try:
            apply_branding(path, logo)
            print(f"[OK] {filename}")
        except Exception as e:
            print(f"[FAIL] {filename}: {e}")

    print(f"\nDone. {len(files)} images processed.")


if __name__ == "__main__":
    main()
