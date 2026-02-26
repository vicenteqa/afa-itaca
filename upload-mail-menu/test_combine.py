#!/usr/bin/env python3
"""
Test local del mode 'combine' del job upload-mail-menu.
Descarga la imatge actual de WordPress, la combina amb la nova imatge local
i guarda el resultat sense pujar res.

Ús:
    python upload-mail-menu/test_combine.py <nova_imatge>

Exemple:
    python upload-mail-menu/test_combine.py /tmp/menu-nou.pdf
    python upload-mail-menu/test_combine.py /tmp/menu-nou.jpg
"""

import io
import os
import sys

import requests
from dotenv import load_dotenv
from pdf2image import convert_from_bytes
from PIL import Image

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), ".env"))

WORDPRESS_URL = os.environ.get("WORDPRESS_URL")
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; MenuUploader/1.0)"}
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "test_result.jpg")


def download_current_menu():
    base_url = f"{WORDPRESS_URL.rstrip('/')}/wp-json/wp/v2/media"
    response = requests.get(base_url, params={"per_page": 100}, headers=HEADERS)
    if response.status_code != 200:
        print(f"Error accedint a la media library: {response.status_code}")
        return None

    for media in response.json():
        slug = media.get("slug", "")
        source_url = media.get("source_url", "")
        if slug.startswith("menjador") or "/menjador" in source_url:
            print(f"Descarregant menú actual: {source_url}")
            img_response = requests.get(source_url, headers=HEADERS)
            if img_response.status_code == 200:
                return Image.open(io.BytesIO(img_response.content))
            else:
                print(f"Error descarregant: {img_response.status_code}")
                return None

    print("No s'ha trobat cap imatge menjador a WordPress")
    return None


def resize_if_needed(image, max_size=1800):
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


def load_new_image(path):
    ext = os.path.splitext(path)[1].lower()
    with open(path, "rb") as f:
        content = f.read()

    if ext == ".pdf":
        print("Convertint PDF a PNG (300 DPI)...")
        images = convert_from_bytes(content, dpi=300, first_page=1, last_page=1)
        if not images:
            raise ValueError("No s'ha pogut convertir el PDF")
        return resize_if_needed(images[0])
    else:
        image = Image.open(io.BytesIO(content))
        if image.mode in ("RGBA", "P"):
            image = image.convert("RGB")
        return resize_if_needed(image)


def combine_images(top_image, bottom_image):
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


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    new_image_path = sys.argv[1]
    if not os.path.exists(new_image_path):
        print(f"Error: no existeix el fitxer '{new_image_path}'")
        sys.exit(1)

    if not WORDPRESS_URL:
        print("Error: WORDPRESS_URL no configurat al .env")
        sys.exit(1)

    print(f"Carregant nova imatge: {new_image_path}")
    new_image = load_new_image(new_image_path)
    print(f"  Mida nova imatge: {new_image.width}x{new_image.height}")

    current_image = download_current_menu()
    if current_image:
        current_image = resize_if_needed(current_image)
        print(f"  Mida imatge actual: {current_image.width}x{current_image.height}")
        print("Combinant actual (dalt) + nova (baix)...")
        result = combine_images(current_image, new_image)
    else:
        print("No hi ha imatge actual, el resultat seria només la nova imatge")
        result = new_image

    print(f"Mida resultat: {result.width}x{result.height}")
    if result.mode in ("RGBA", "P"):
        result = result.convert("RGB")
    result.save(OUTPUT_PATH, format="JPEG", quality=85, optimize=True)
    print(f"\nResultat guardat a: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
