#!/usr/bin/env python3
"""
Splits the combined menjador.png in WordPress, keeping only the bottom half.
Intended to run on the 1st of each month to remove the previous month's menu
from the combined image, leaving only the current month's menu.
"""

import os
import sys
import io
import re
import time
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

WORDPRESS_URL = os.environ.get("WORDPRESS_URL")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MenuUploader/1.0)"}
MENU_PAGE_ID = 3224


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
        source_url = data.get("source_url", "")
        print(f"Uploaded: {filename} -> {source_url}")
        return source_url
    else:
        print(f"Error uploading: {response.status_code} - {response.text}")
        return None


def update_page_iframe(new_source_url, auth):
    """Update the iframe src in the WordPress menu page to point to the new image URL."""
    url = f"{WORDPRESS_URL.rstrip('/')}/wp-json/wp/v2/pages/{MENU_PAGE_ID}"

    response = requests.get(url, auth=auth, headers=HEADERS)
    if response.status_code != 200:
        print(f"Error fetching page {MENU_PAGE_ID}: {response.status_code}")
        return False

    page = response.json()
    content = page["content"]["raw"]

    new_content = re.sub(
        r'https?://[^"]*?/wp-content/uploads/[^"]*menjador[^"]*\.png',
        new_source_url,
        content,
    )

    if new_content == content:
        print("Warning: Could not find menjador iframe URL to update in page content")
        return False

    response = requests.post(
        url,
        json={"content": new_content},
        auth=auth,
        headers=HEADERS,
    )

    if response.status_code == 200:
        print(f"Updated page iframe to: {new_source_url}")
        return True
    else:
        print(f"Error updating page: {response.status_code} - {response.text[:200]}")
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

    # Extract the second month from the combined filename (e.g. menjador020326.png -> 03, 26)
    # Combined: menjadorMMmmYY.png (MM=current month, mm=next month, YY=year)
    # Single:   menjadorMMYY.png
    basename = source_url.rsplit("/", 1)[-1]  # e.g. "menjador020326.png"
    match = re.match(r'menjador(\d{2})(\d{2})(\d{2})\.png', basename)
    if match:
        # Combined image: use second month + year
        second_month = match.group(2)
        year = match.group(3)
        target_filename = f"menjador{second_month}{year}.png"
        print(f"Combined filename detected: {basename} -> keeping month {second_month}")
    else:
        # Single month image or unexpected format, keep as-is
        print(f"Single-month filename: {basename}, nothing to rename")
        target_filename = basename

    # Delete old and upload new
    if delete_media(media_id, auth):
        print(f"Deleted old image (ID: {media_id})")
        time.sleep(2)
    else:
        print("Warning: Could not delete old image, uploading anyway")

    new_source_url = upload_image(target_filename, bottom, auth)
    if new_source_url:
        update_page_iframe(new_source_url, auth)
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
