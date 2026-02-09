#!/usr/bin/env python3
"""
Splits the combined menjador.png in WordPress, keeping only the bottom half.
Intended to run on the 1st of each month to remove the previous month's menu
from the combined image, leaving only the current month's menu.
"""

import os
import sys
import io
import time
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

WORDPRESS_URL = os.environ.get("WORDPRESS_URL")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")

TARGET_FILENAME = "menjador.png"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MenuUploader/1.0)"}


def find_menu_media():
    """Find the menjador image in WordPress media library. Returns (media_id, source_url) or (None, None)."""
    base_url = f"{WORDPRESS_URL.rstrip('/')}/wp-json/wp/v2/media"
    response = requests.get(base_url, params={"per_page": 100}, headers=HEADERS)

    if response.status_code != 200:
        print(f"Error fetching media library: {response.status_code}")
        return None, None

    for media in response.json():
        slug = media.get("slug", "")
        source_url = media.get("source_url", "")
        if slug.startswith("menjador") or "/menjador" in source_url:
            return media.get("id"), source_url

    return None, None


def download_image(url):
    """Download an image from a URL and return it as a PIL Image."""
    response = requests.get(url, headers=HEADERS)
    if response.status_code != 200:
        print(f"Error downloading image: {response.status_code}")
        return None
    return Image.open(io.BytesIO(response.content))


def split_bottom_half(image):
    """Crop the bottom half of an image."""
    width, height = image.size
    top = height // 2
    return image.crop((0, top, width, height))


def delete_media(media_id, auth):
    """Delete a file from the WordPress media library."""
    url = f"{WORDPRESS_URL.rstrip('/')}/wp-json/wp/v2/media/{media_id}"
    response = requests.delete(url, params={"force": True}, auth=auth, headers=HEADERS)
    if response.status_code != 200:
        print(f"Delete error: {response.status_code} - {response.text[:200]}")
    return response.status_code == 200


def upload_image(filename, image, auth):
    """Upload a PIL Image to WordPress as PNG."""
    png_buffer = io.BytesIO()
    image.save(png_buffer, format="PNG", optimize=True)
    content = png_buffer.getvalue()

    url = f"{WORDPRESS_URL.rstrip('/')}/wp-json/wp/v2/media"
    headers = {
        **HEADERS,
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": "image/png",
    }

    response = requests.post(url, headers=headers, data=content, auth=auth)

    if response.status_code == 201:
        data = response.json()
        print(f"Uploaded: {filename} -> {data.get('source_url', 'URL not available')}")
        return True
    else:
        print(f"Error uploading: {response.status_code} - {response.text}")
        return False


def main():
    auth = HTTPBasicAuth(WORDPRESS_USER, WORDPRESS_APP_PASSWORD)

    # Find current menu
    media_id, source_url = find_menu_media()
    if not media_id:
        print("No menjador image found in WordPress. Nothing to split.")
        return

    print(f"Found menu: {source_url} (ID: {media_id})")

    # Download it
    image = download_image(source_url)
    if not image:
        return

    print(f"Image size: {image.width}x{image.height}")

    # Split - keep bottom half
    bottom = split_bottom_half(image)
    print(f"Cropped to bottom half: {bottom.width}x{bottom.height}")

    # Delete old and upload new
    if delete_media(media_id, auth):
        print(f"Deleted old image (ID: {media_id})")
        time.sleep(2)
    else:
        print("Warning: Could not delete old image, uploading anyway")

    upload_image(TARGET_FILENAME, bottom, auth)
    print("Done.")


def validate_config():
    """Validate that all environment variables are configured."""
    required = [
        ("WORDPRESS_URL", WORDPRESS_URL),
        ("WORDPRESS_USER", WORDPRESS_USER),
        ("WORDPRESS_APP_PASSWORD", WORDPRESS_APP_PASSWORD),
    ]

    missing = [name for name, value in required if not value]

    if missing:
        print(f"Error: Missing environment variables: {', '.join(missing)}")
        sys.exit(1)


if __name__ == "__main__":
    validate_config()
    main()
