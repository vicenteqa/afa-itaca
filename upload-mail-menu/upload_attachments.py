#!/usr/bin/env python3
"""
Downloads attachments from emails of a specific sender and uploads them to WordPress.
"""

import imaplib
import email
import os
import sys
from email.header import decode_header
import requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

# Configuration from environment variables
GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
ALLOWED_SENDER = os.environ.get("ALLOWED_SENDER")
WORDPRESS_URL = os.environ.get("WORDPRESS_URL")
WORDPRESS_USER = os.environ.get("WORDPRESS_USER")
WORDPRESS_APP_PASSWORD = os.environ.get("WORDPRESS_APP_PASSWORD")

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def get_filename(part):
    """Extract the filename from the attachment."""
    filename = part.get_filename()
    if filename:
        decoded = decode_header(filename)
        if decoded[0][1]:
            return decoded[0][0].decode(decoded[0][1])
        return decoded[0][0] if isinstance(decoded[0][0], str) else decoded[0][0].decode()
    return None


def find_existing_media(filename, auth):
    """Search if a file with the same name already exists in WordPress."""
    url = f"{WORDPRESS_URL.rstrip('/')}/wp-json/wp/v2/media"
    response = requests.get(url, params={"search": filename}, auth=auth)

    if response.status_code == 200:
        for media in response.json():
            # Compare filename (without path)
            source_url = media.get("source_url", "")
            if source_url.endswith(f"/{filename}") or media.get("title", {}).get("rendered") == os.path.splitext(filename)[0]:
                return media.get("id")
    return None


def delete_media(media_id, auth):
    """Delete a file from the WordPress media library."""
    url = f"{WORDPRESS_URL.rstrip('/')}/wp-json/wp/v2/media/{media_id}"
    response = requests.delete(url, params={"force": True}, auth=auth)
    return response.status_code == 200


def upload_to_wordpress(filename, content, content_type):
    """Upload a file to WordPress via REST API, replacing if it already exists."""
    auth = HTTPBasicAuth(WORDPRESS_USER, WORDPRESS_APP_PASSWORD)

    # Find and delete existing file
    existing_id = find_existing_media(filename, auth)
    if existing_id:
        if delete_media(existing_id, auth):
            print(f"  Previous file deleted (ID: {existing_id})")
        else:
            print(f"  Warning: Could not delete previous file (ID: {existing_id})")

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
            content_type = part.get_content_type()

            print(f"  Attachment found: {filename}")

            # Rename to menjador with the original extension
            ext = os.path.splitext(filename)[1].lower()
            new_filename = f"menjador{ext}"
            print(f"  Renaming to: {new_filename}")

            if upload_to_wordpress(new_filename, content, content_type):
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
