import os
import psycopg2
from google import genai
from google.genai import types

API_KEY = "AIzaSyDK5oeV0s7P0qHIK7V6QCy-LEFy1q9mHl4"
OUTPUT_DIR = "C:/ClaudeProjects/OpenVoorSocials/backend/media/posts/2026/15"
STYLE_SUFFIX = (
    "Warm lifestyle photography, realistic, natural lighting, teal and navy color accents, "
    "Belgian urban or nature setting, inclusive, adults aged 30-50, candid and authentic feel, "
    "no text overlays, no logos, high quality."
)

DB_CONFIG = {
    "host": "192.168.0.172",
    "port": 5433,
    "dbname": "app_openvoorsocials",
    "user": "app_openvoorsocials",
    "password": "8xZnQBHYxalYEMIpu6naWgMI",
}

os.makedirs(OUTPUT_DIR, exist_ok=True)

conn = psycopg2.connect(**DB_CONFIG)
cur = conn.cursor()

cur.execute(
    "SELECT id, image_prompt, week_number, year FROM content_socialpost "
    "WHERE image_path = '' AND week_number = 15 AND year = 2026"
)
posts = cur.fetchall()
print(f"Fetched {len(posts)} posts to process.\n")

client = genai.Client(api_key=API_KEY)

success = 0
failed = 0

for post_id, image_prompt, week_number, year in posts:
    try:
        print(f"Generating image for post {post_id} ...")
        full_prompt = f"{image_prompt}. {STYLE_SUFFIX}"

        response = client.models.generate_images(
            model="imagen-4.0-generate-001",
            prompt=full_prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio="1:1",
                safety_filter_level="BLOCK_LOW_AND_ABOVE",
                person_generation="ALLOW_ADULT",
            ),
        )

        image_bytes = response.generated_images[0].image.image_bytes
        file_path = os.path.join(OUTPUT_DIR, f"{post_id}.png")

        with open(file_path, "wb") as f:
            f.write(image_bytes)

        relative_path = f"posts/2026/15/{post_id}.png"
        cur.execute(
            "UPDATE content_socialpost SET image_path = %s WHERE id = %s",
            (relative_path, str(post_id)),
        )
        conn.commit()

        print(f"[OK] post {post_id} — saved to {relative_path}")
        success += 1

    except Exception as e:
        conn.rollback()
        print(f"[ERROR] post {post_id} — {e}")
        failed += 1

cur.close()
conn.close()

print(f"\nDone. {success} succeeded, {failed} failed.")
