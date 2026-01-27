#!/usr/bin/env python3
"""
Downloads attachments from emails of a specific sender and uploads them to WordPress.
"""

import imaplib
import email
import os
import sys
import io
import time
from email.header import decode_header
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
from PIL import Image

load_dotenv()

# Configuration from environment variables
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
ALLOWED_SENDER = os.environ.get("ALLOWED_SENDER")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
TARGET_FILENAME = "menjador.pdf"


def get_filename(part):
    """Extract the filename from the attachment."""
    filename = part.get_filename()
    if filename:
        decoded = decode_header(filename)
        if decoded[0][1]:
            return decoded[0][0].decode(decoded[0][1])
        return decoded[0][0] if isinstance(decoded[0][0], str) else decoded[0][0].decode()
    return None


def convert_image_to_pdf(image_content):
    """Convert image bytes to PDF bytes."""
    image = Image.open(io.BytesIO(image_content))
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    pdf_buffer = io.BytesIO()
    image.save(pdf_buffer, format="PDF")
    return pdf_buffer.getvalue()


def find_all_existing_media():
    """Find all menjador*.pdf files in WordPress media library."""
    base_url = f"{WORDPRESS_URL.rstrip('/')}/wp-json/wp/v2/media"
    found_ids = []

    # List media without auth (public endpoint) but with User-Agent
    headers = {"User-Agent": "Mozilla/5.0 (compatible; MenuUploader/1.0)"}
    response = requests.get(base_url, params={"per_page": 100}, headers=headers)
    print(f"  API status: {response.status_code}, items returned: {len(response.json()) if response.status_code == 200 else 0}")

    if response.status_code == 200:
        for media in response.json():
            source_url = media.get("source_url", "")
            slug = media.get("slug", "")
            # Match menjador, menjador-1, menjador-2, etc.
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

    # Find and delete all existing menjador files (except the original 2025/12 one)
    existing_ids = find_all_existing_media()
    for existing_id in existing_ids:
        if delete_media(existing_id, auth):
            print(f"  Deleted file (ID: {existing_id})")
        else:
            print(f"  Warning: Could not delete file (ID: {existing_id})")

    # Wait for WordPress to fully process deletions
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


def process_emails():
    """Connect to Gmail, search emails and process attachments."""
    print(f"Connecting to Gmail as {GMAIL_USER}...")

    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    mail.select("INBOX")

    # Search unread emails from the allowed sender
    search_criteria = f'(UNSEEN FROM "{ALLOWED_SENDER}")'
    status, messages = mail.search(None, search_criteria)

    if status != "OK":
        print("Error searching emails")
        mail.logout()
        return

    email_ids = messages[0].split()
    print(f"Found {len(email_ids)} unread emails from {ALLOWED_SENDER}")

    total_uploaded = 0

    for email_id in email_ids:
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

            content = part.get_payload(decode=True)

            print(f"  Attachment found: {filename}")

            # Convert images to PDF if needed
            if ext in {".jpg", ".jpeg", ".png"}:
                print(f"  Converting image to PDF...")
                content = convert_image_to_pdf(content)

            print(f"  Uploading as: {TARGET_FILENAME}")

            if upload_to_wordpress(TARGET_FILENAME, content, "application/pdf"):
                total_uploaded += 1

        # Mark as read
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
