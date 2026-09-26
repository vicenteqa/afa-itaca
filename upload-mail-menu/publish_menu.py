#!/usr/bin/env python3
"""
Descarrega el PDF del menú de l'últim correu no llegit de l'adreça
autoritzada, i el desa a public/uploads/menjador.pdf (es conserva tal
qual per si cal reprocessar-lo), en genera una imatge (menjador.jpg) amb
la primera pàgina -que és el que es mostra a la pàgina /menu-del-mes-, i
en extreu el menú dia a dia (menjador.json) per al widget "què hi ha
avui". El workflow de GitHub Actions és qui es fa càrrec de fer commit i
push del canvi (aquest script només toca els fitxers locals).

Ús:
    python publish_menu.py
"""

import email
import imaplib
import json
import os
import sys
from email.header import decode_header

from dotenv import load_dotenv
from pdf2image import convert_from_bytes
from PIL import Image

from ocr_menu import extract_menu

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

GMAIL_USER = os.environ.get("GMAIL_USER")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
ALLOWED_SENDER = os.environ.get("ALLOWED_SENDER")

UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "..", "public", "uploads")
PDF_PATH = os.path.join(UPLOADS_DIR, "menjador.pdf")
IMAGE_PATH = os.path.join(UPLOADS_DIR, "menjador.jpg")
JSON_PATH = os.path.join(UPLOADS_DIR, "menjador.json")


def get_filename(part):
    filename = part.get_filename()
    if not filename:
        return None
    decoded = decode_header(filename)
    if decoded[0][1]:
        return decoded[0][0].decode(decoded[0][1])
    return decoded[0][0] if isinstance(decoded[0][0], str) else decoded[0][0].decode()


def find_latest_pdf():
    """Connect to Gmail and return the PDF bytes of the most recent unread
    email's first PDF attachment, or None if there's nothing to do."""
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

    content = None
    for part in msg.walk():
        if part.get_content_maintype() == "multipart":
            continue
        filename = get_filename(part)
        if not filename:
            continue
        if os.path.splitext(filename)[1].lower() != ".pdf":
            print(f"  Ignorant {filename} (no és un PDF)")
            continue
        print(f"  PDF trobat: {filename}")
        content = part.get_payload(decode=True)
        break

    mail.store(email_id, "+FLAGS", "\\Seen")
    mail.logout()
    return content


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


def render_first_page(pdf_content):
    """Render the PDF's first page as a resized RGB image, for display."""
    pages = convert_from_bytes(pdf_content, dpi=300, first_page=1, last_page=1)
    if not pages:
        raise ValueError("No s'ha pogut convertir el PDF a imatge")
    return resize_if_needed(pages[0].convert("RGB"))


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

    content = find_latest_pdf()
    if content is None:
        print("Cap correu nou amb un PDF adjunt. Sortint.")
        return

    os.makedirs(UPLOADS_DIR, exist_ok=True)

    with open(PDF_PATH, "wb") as f:
        f.write(content)
    print(f"PDF desat a {PDF_PATH}")

    image = render_first_page(content)
    image.save(IMAGE_PATH, format="JPEG", quality=85, optimize=True)
    print(f"Imatge desada a {IMAGE_PATH}")

    try:
        menu = extract_menu(PDF_PATH)
    except Exception as exc:  # noqa: BLE001 - a failed extraction shouldn't break the publish
        print(f"Avís: no s'ha pogut extreure el menú dia a dia ({exc}). "
              "Es manté el JSON anterior (si n'hi havia).")
        return

    with open(JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(menu, f, ensure_ascii=False, indent=2)
    print(f"Menú dia a dia desat a {JSON_PATH} ({len(menu['days'])} dies, "
          f"confiança {menu['date_offset_confidence']})")


if __name__ == "__main__":
    main()
