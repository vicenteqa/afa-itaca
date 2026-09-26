#!/usr/bin/env python3
"""
Descarrega l'adjunt del menú (PDF o imatge) de l'últim correu no llegit de
l'adreça autoritzada, i el desa com public/uploads/menjador.jpg, reemplaçant
el menú del mes anterior. El workflow de GitHub Actions és qui es fa càrrec
de fer commit i push del canvi (aquest script només toca el fitxer local).

Ús:
    python publish_menu.py
"""

import email
import imaplib
import io
import os
import sys
from email.header import decode_header

from dotenv import load_dotenv
from pdf2image import convert_from_bytes
from PIL import Image

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
ALLOWED_SENDER = os.environ.get("ALLOWED_SENDER")

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
TARGET_PATH = os.path.join(os.path.dirname(__file__), "..", "public", "uploads", "menjador.jpg")


def get_filename(part):
    filename = part.get_filename()
    if not filename:
        return None
    decoded = decode_header(filename)
    if decoded[0][1]:
        return decoded[0][0].decode(decoded[0][1])
    return decoded[0][0] if isinstance(decoded[0][0], str) else decoded[0][0].decode()


def resize_if_needed(image, max_size=1800):
    """Resize image if any dimension exceeds max_size, preserving aspect ratio."""
    width, height = image.size
    if width <= max_size and height <= max_size:
        return image
    if width > height:
        new_width, new_height = max_size, int(height * max_size / width)
    else:
        new_height, new_width = max_size, int(width * max_size / height)
    return image.resize((new_width, new_height), Image.LANCZOS)


def attachment_to_image(content, ext):
    """Convert the attachment bytes to a PIL Image, handling PDF and image formats."""
    if ext == ".pdf":
        print("  Convertint PDF a imatge (300 DPI)...")
        pages = convert_from_bytes(content, dpi=300, first_page=1, last_page=1)
        if not pages:
            raise ValueError("No s'ha pogut convertir el PDF")
        return resize_if_needed(pages[0].convert("RGB"))

    image = Image.open(io.BytesIO(content))
    if image.mode in ("RGBA", "P"):
        image = image.convert("RGB")
    return resize_if_needed(image)


def find_latest_attachment():
    """Connect to Gmail and return (filename, ext, content) of the most recent
    unread email's first valid attachment, or None if there's nothing to do."""
    print(f"Connectant a Gmail com a {GMAIL_USER}...")
    mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
    mail.login(GMAIL_USER, GMAIL_APP_PASSWORD)
    mail.select("INBOX")

    if ALLOWED_SENDER == "*":
        criteria = "(UNSEEN)"
        sender_desc = "qualsevol remitent"
    else:
        criteria = f'(UNSEEN FROM "{ALLOWED_SENDER}")'
        sender_desc = ALLOWED_SENDER

    status, messages = mail.search(None, criteria)
    if status != "OK":
        mail.logout()
        raise RuntimeError("Error cercant correus")

    email_ids = messages[0].split()
    print(f"Trobats {len(email_ids)} correus no llegits de {sender_desc}")

    if not email_ids:
        mail.logout()
        return None

    if len(email_ids) > 1:
        older = email_ids[:-1]
        print(f"Marcant {len(older)} correus antics com a llegits (s'ometen)...")
        for email_id in older:
            mail.store(email_id, "+FLAGS", "\\Seen")

    email_id = email_ids[-1]
    status, msg_data = mail.fetch(email_id, "(RFC822)")
    if status != "OK":
        mail.logout()
        raise RuntimeError("Error descarregant el correu")

    msg = email.message_from_bytes(msg_data[0][1])
    subject = decode_header(msg["Subject"])[0][0]
    if isinstance(subject, bytes):
        subject = subject.decode()
    print(f"Processant: {subject}")

    result = None
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = get_filename(part)
        if not filename:
            continue
        ext = os.path.splitext(filename)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            print(f"  Ignorant {filename} (extensió no permesa)")
            continue
        print(f"  Adjunt trobat: {filename}")
        result = (filename, ext, part.get_payload(decode=True))
        break

    mail.store(email_id, "+FLAGS", "\\Seen")
    mail.logout()
    return result


def validate_config():
    required = [
        ("GMAIL_USER", GMAIL_USER),
        ("GMAIL_APP_PASSWORD", GMAIL_APP_PASSWORD),
        ("ALLOWED_SENDER", ALLOWED_SENDER),
    ]
    missing = [name for name, value in required if not value]
    if missing:
        print(f"Error: falten variables d'entorn: {', '.join(missing)}")
        sys.exit(1)


def main():
    validate_config()

    attachment = find_latest_attachment()
    if attachment is None:
        print("Cap correu nou amb adjunt vàlid. Sortint.")
        return

    filename, ext, content = attachment
    image = attachment_to_image(content, ext)

    os.makedirs(os.path.dirname(TARGET_PATH), exist_ok=True)
    image.save(TARGET_PATH, format="JPEG", quality=85, optimize=True)
    print(f"Menú desat a {TARGET_PATH}")


if __name__ == "__main__":
    main()
