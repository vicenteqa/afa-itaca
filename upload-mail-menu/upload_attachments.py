#!/usr/bin/env python3
"""
Downloads menu attachments from emails and uploads them to WordPress.
During the last 6 days of the month, combines the current menu (top)
with the new one (bottom). During the first 5 days, uploads directly
(late menu for the current month).
"""

import imaplib
import email
import os
import re
import sys
import io
import time
import calendar
from datetime import date, datetime
from email.header import decode_header
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from PIL import Image
from pdf2image import convert_from_bytes

load_dotenv()

# Configuration from environment variables
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
ALLOWED_SENDER = os.environ.get("ALLOWED_SENDER")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
TARGET_FILENAME = "menjador.jpg"
MENU_PAGE_ID = 3224


def is_end_of_month():
    """Check if today is within the last 6 days of the month."""
    today = date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    return today.day >= last_day - 6


def is_start_of_month():
    """Check if today is within the first 5 days of the month."""
    return date.today().day <= 5


def get_filename(part):
    """Extract the filename from the attachment."""
    filename = part.get_filename()
    if filename:
        decoded = decode_header(filename)
        if decoded[0][1]:
            return decoded[0][0].decode(decoded[0][1])
        return decoded[0][0] if isinstance(decoded[0][0], str) else decoded[0][0].decode()
    return None


def resize_if_needed(image, max_size=1800):
    """Resize image if any dimension exceeds max_size, preserving aspect ratio."""
    width, height = image.size
    if width <= max_size and height <= max_size:
        return image

    if width > height:
        new_width = max_size
        new_height = int(height * max_size / width)
    else:
        new_height = max_size
        new_width = int(width * max_size / height)

    return image.resize((new_width, new_height), Image.LANCZOS)


def attachment_to_image(content, ext):
    """Convert attachment bytes to a PIL Image, handling PDF and image formats."""
    if ext == ".pdf":
        print("  Converting PDF to PNG (300 DPI)...")
        images = convert_from_bytes(content, dpi=300, first_page=1, last_page=1)
        if not images:
            raise ValueError("Could not convert PDF to image")
        return resize_if_needed(images[0])
    else:
        image = Image.open(io.BytesIO(content))
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        return resize_if_needed(image)


def image_to_jpeg_bytes(image, quality=85):
    """Convert a PIL Image to JPEG bytes."""
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    jpeg_buffer = io.BytesIO()
    image.save(jpeg_buffer, format="JPEG", quality=quality, optimize=True)
    return jpeg_buffer.getvalue()


def download_current_menu():
    """Download the current menjador image from WordPress media library."""
    base_url = f"{WORDPRESS_URL.rstrip('/')}/wp-json/wp/v2/media"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; MenuUploader/1.0)"}
    response = requests.get(base_url, params={"per_page": 100}, headers=headers)

    if response.status_code != 200:
        print("  Could not fetch media library")
        return None

    for media in response.json():
        slug = media.get("slug", "")
        source_url = media.get("source_url", "")
        if (slug.startswith("menjador") or "/menjador" in source_url) and "scaled" not in slug:
            print(f"  Downloading current menu from: {source_url}")
            img_response = requests.get(source_url, headers=headers)
            if img_response.status_code == 200:
                return Image.open(io.BytesIO(img_response.content))
            else:
                print(f"  Error downloading image: {img_response.status_code}")
                return None

    print("  No current menu found in WordPress")
    return None


def combine_images(top_image, bottom_image):
    """Combine two images vertically (top above bottom), scaling to same width."""
    target_width = max(top_image.width, bottom_image.width)

    if top_image.width != target_width:
        ratio = target_width / top_image.width
        top_image = top_image.resize(
            (target_width, int(top_image.height * ratio)), Image.LANCZOS
        )
    if bottom_image.width != target_width:
        ratio = target_width / bottom_image.width
        bottom_image = bottom_image.resize(
            (target_width, int(bottom_image.height * ratio)), Image.LANCZOS
        )

    combined_height = top_image.height + bottom_image.height
    combined = Image.new("RGB", (target_width, combined_height), (255, 255, 255))
    combined.paste(top_image, (0, 0))
    combined.paste(bottom_image, (0, top_image.height))

    return combined


def find_all_existing_media():
    """Find all menjador* files in WordPress media library."""
    base_url = f"{WORDPRESS_URL.rstrip('/')}/wp-json/wp/v2/media"
    found_ids = []

    headers = {"User-Agent": "Mozilla/5.0 (compatible; MenuUploader/1.0)"}
    response = requests.get(base_url, params={"per_page": 100}, headers=headers)
    print(f"  API status: {response.status_code}, items returned: {len(response.json()) if response.status_code == 200 else 0}")

    if response.status_code == 200:
        for media in response.json():
            source_url = media.get("source_url", "")
            slug = media.get("slug", "")
            if slug.startswith("menjador") or "/menjador" in source_url:
                media_id = media.get("id")
                print(f"  Found: {source_url} (ID: {media_id})")
                found_ids.append(media_id)

    if not found_ids:
        print("  No existing menjador files to delete")

    return found_ids


def delete_media(media_id, auth):
    """Delete a file from the WordPress media library."""
    url = f"{WORDPRESS_URL.rstrip('/')}/wp-json/wp/v2/media/{media_id}"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; MenuUploader/1.0)"}
    response = requests.delete(url, params={"force": True}, auth=auth, headers=headers)
    if response.status_code != 200:
        print(f"    Delete error: {response.status_code} - {response.text[:200]}")
    return response.status_code == 200


def upload_to_wordpress(filename, content, content_type):
    """Upload a file to WordPress via REST API, replacing if it already exists."""
    auth = HTTPBasicAuth(WORDPRESS_USER, WORDPRESS_APP_PASSWORD)

    existing_ids = find_all_existing_media()
    for existing_id in existing_ids:
        if delete_media(existing_id, auth):
            print(f"  Deleted file (ID: {existing_id})")
        else:
            print(f"  Warning: Could not delete file (ID: {existing_id})")

    if existing_ids:
        print("  Waiting for WordPress to process deletions...")
        time.sleep(2)

    url = f"{WORDPRESS_URL.rstrip('/')}/wp-json/wp/v2/media"

    headers = {
        "Content-Disposition": f'attachment; filename="{filename}"',
        "Content-Type": content_type,
    }

    response = requests.post(url, headers=headers, data=content, auth=auth)

    if response.status_code == 201:
        data = response.json()
        print(f"  Uploaded: {filename} -> {data.get('source_url', 'URL not available')}")
        return True
    else:
        print(f"  Error uploading {filename}: {response.status_code} - {response.text}")
        return False


def update_page_iframe(version):
    """Update the menu iframe URL in the WordPress page with a cache-busting version."""
    auth = HTTPBasicAuth(WORDPRESS_USER, WORDPRESS_APP_PASSWORD)
    headers = {"User-Agent": "Mozilla/5.0 (compatible; MenuUploader/1.0)"}
    base = WORDPRESS_URL.rstrip('/')

    response = requests.get(
        f"{base}/wp-json/wp/v2/pages/{MENU_PAGE_ID}",
        params={"context": "edit"},
        auth=auth,
        headers=headers,
    )
    if response.status_code != 200:
        print(f"  Could not fetch page: {response.status_code}")
        return False

    elementor_data = response.json().get("meta", {}).get("_elementor_data", "")
    if not elementor_data:
        print("  No Elementor data found in page")
        return False

    # Replace only the menjador file directly in /uploads/ (not subfolders like 2022/05/menjador2.jpg)
    new_elementor_data = re.sub(
        r'\\/uploads\\/menjador[^\\/\\"]*',
        f'\\/uploads\\/{TARGET_FILENAME}?v={version}',
        elementor_data,
    )

    if new_elementor_data == elementor_data:
        print("  iframe URL unchanged (pattern not found)")
        return False

    update_resp = requests.post(
        f"{base}/wp-json/wp/v2/pages/{MENU_PAGE_ID}",
        auth=auth,
        headers={**headers, "Content-Type": "application/json"},
        json={"meta": {"_elementor_data": new_elementor_data}},
    )
    if update_resp.status_code != 200:
        print(f"  Error updating page: {update_resp.status_code}")
        return False

    print(f"  iframe updated -> {TARGET_FILENAME}?v={version}")

    cache_resp = requests.delete(
        f"{base}/wp-json/elementor/v1/cache",
        auth=auth,
        headers=headers,
    )
    print(f"  Elementor cache cleared (status: {cache_resp.status_code})")
    return True


def process_emails():
    """Connect to Gmail, search emails and process attachments."""
    print(f"Connecting to Gmail as {GMAIL_USER}...")

    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    mail.select("INBOX")

    if ALLOWED_SENDER == "*":
        search_criteria = "(UNSEEN)"
        sender_desc = "any sender"
    else:
        search_criteria = f'(UNSEEN FROM "{ALLOWED_SENDER}")'
        sender_desc = ALLOWED_SENDER
    status, messages = mail.search(None, search_criteria)

    if status != "OK":
        print("Error searching emails")
        mail.logout()
        return

    email_ids = messages[0].split()
    print(f"Found {len(email_ids)} unread emails from {sender_desc}")

    if not email_ids:
        print("No emails to process.")
        mail.logout()
        return

    if len(email_ids) > 1:
        older_emails = email_ids[:-1]
        print(f"Marking {len(older_emails)} older emails as read (skipping processing)...")
        for email_id in older_emails:
            mail.store(email_id, "+FLAGS", "\\Seen")

    most_recent_id = email_ids[-1]
    total_uploaded = 0

    # Determine upload mode based on trigger type and day of month
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    if event_name == "workflow_dispatch":
        mode = "combine"
        print(f"Mode: COMBINE (manual trigger - always combines)")
    elif is_end_of_month():
        mode = "combine"
        print(f"Mode: COMBINE (last 6 days of month - will merge current + new menu)")
    elif is_start_of_month():
        mode = "direct"
        print(f"Mode: DIRECT (first 5 days - late menu upload)")
    else:
        mode = "direct"
        print(f"Mode: DIRECT (mid-month upload)")

    for email_id in [most_recent_id]:
        status, msg_data = mail.fetch(email_id, "(RFC822)")

        if status != "OK":
            continue

        raw_email = msg_data[0][1]
        msg = email.message_from_bytes(raw_email)

        subject = decode_header(msg["Subject"])[0][0]
        if isinstance(subject, bytes):
            subject = subject.decode()
        print(f"\nProcessing: {subject}")

        for part in msg.walk():
            if part.get_content_maintype() == "multipart":
                continue

            filename = get_filename(part)
            if not filename:
                continue

            ext = os.path.splitext(filename)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                print(f"  Ignoring {filename} (extension not allowed)")
                continue

            raw_content = part.get_payload(decode=True)
            print(f"  Attachment found: {filename}")

            new_image = attachment_to_image(raw_content, ext)

            if mode == "combine":
                current_image = download_current_menu()
                if current_image:
                    current_image = resize_if_needed(current_image)
                    print("  Combining current menu (top) + new menu (bottom)...")
                    combined = combine_images(current_image, new_image)
                    content = image_to_jpeg_bytes(combined)
                else:
                    print("  No current menu found, uploading new menu directly")
                    content = image_to_jpeg_bytes(new_image)
            else:
                content = image_to_jpeg_bytes(new_image)

            print(f"  Uploading as: {TARGET_FILENAME}")

            if upload_to_wordpress(TARGET_FILENAME, content, "image/jpeg"):
                total_uploaded += 1
                version = datetime.now().strftime("%Y%m%d%H%M")
                print(f"  Updating page iframe (v={version})...")
                update_page_iframe(version)

        mail.store(email_id, "+FLAGS", "\\Seen")

    mail.logout()
    print(f"\nProcess completed. {total_uploaded} files uploaded to WordPress.")


def validate_config():
    """Validate that all environment variables are configured."""
    required = [
        ("GMAIL_USER", GMAIL_USER),
        ("GMAIL_APP_PASSWORD", GMAIL_APP_PASSWORD),
        ("ALLOWED_SENDER", ALLOWED_SENDER),
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
    process_emails()
