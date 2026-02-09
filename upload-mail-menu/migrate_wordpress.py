#!/usr/bin/env python3
"""
Migrates content from WordPress to Astro site.
Fetches posts and pages from WordPress REST API and converts them to markdown.
Downloads images locally and updates references.
"""

import os
import re
import html
import hashlib
import requests
from urllib.parse import urlparse
from datetime import datetime
from dotenv import load_dotenv
from markdownify import markdownify as md

load_dotenv()

WORDPRESS_URL = os.environ.get("WORDPRESS_URL", "https://www.afaitaca.org")
ASTRO_ROOT = os.path.join(os.path.dirname(__file__), "..")
ASTRO_CONTENT_DIR = os.path.join(ASTRO_ROOT, "src", "content")
ASTRO_PUBLIC_DIR = os.path.join(ASTRO_ROOT, "public")
IMAGES_DIR = os.path.join(ASTRO_PUBLIC_DIR, "images", "wp")

# Track downloaded images to avoid duplicates
downloaded_images = {}

# Map WordPress page slugs to Astro content locations
PAGE_MAPPING = {
    # Comissions
    "espai-migdia": ("comissions", "menjador", {"icon": "utensils", "order": 1}),
    "acollida-matinal": ("comissions", "acollida-matinal", {"icon": "sun", "order": 2}),
    "extraescolars": ("comissions", "extraescolars", {"icon": "futbol", "order": 3}),
    "casals": ("comissions", "casals", {"icon": "campground", "order": 4}),
    "festes": ("comissions", "festes", {"icon": "cake-candles", "order": 5}),
    "formacio-i-families": ("comissions", "formacio", {"icon": "graduation-cap", "order": 6}),
    "comunicacio": ("comissions", "comunicacio", {"icon": "bullhorn", "order": 7}),
    "medi-ambient": ("comissions", "medi-ambient", {"icon": "leaf", "order": 8}),
    "patis": ("comissions", "patis", {"icon": "tree", "order": 9}),
    # Pages
    "lafa": ("pages", "lafa", {}),
    "contacte": ("pages", "contacte", {}),
    "documents-dinteres": ("pages", "documents", {}),
    "familia-socia": ("pages", "familia-socia", {}),
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
}

HEADERS_IMAGE = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


def download_image(url):
    """Download an image and return the local path."""
    if not url:
        return ""

    # Skip non-WordPress URLs (like emoji SVGs)
    if "w.org/images" in url or "s.w.org" in url:
        return url

    # Check if already downloaded
    if url in downloaded_images:
        return downloaded_images[url]

    try:
        # Parse URL to get filename
        parsed = urlparse(url)
        path_parts = parsed.path.split("/")
        original_filename = path_parts[-1] if path_parts else "image.jpg"

        # Create a unique filename based on URL hash + original name
        url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
        filename = f"{url_hash}-{original_filename}"

        # Download image
        response = requests.get(url, headers=HEADERS_IMAGE, timeout=30)
        if response.status_code != 200:
            print(f"    Warning: Could not download {url} (status {response.status_code})")
            return url

        # Save image
        os.makedirs(IMAGES_DIR, exist_ok=True)
        local_path = os.path.join(IMAGES_DIR, filename)

        with open(local_path, "wb") as f:
            f.write(response.content)

        # Return path relative to public folder (for use in markdown)
        relative_path = f"/images/wp/{filename}"
        downloaded_images[url] = relative_path

        return relative_path

    except Exception as e:
        print(f"    Warning: Error downloading {url}: {e}")
        return url


def replace_image_urls(content):
    """Find all WordPress image URLs in content and replace with local paths."""
    # Pattern to match WordPress image URLs
    wp_image_pattern = r'(https?://(?:www\.)?afaitaca\.org/wp-content/uploads/[^\s\)\]"\']+)'

    def replace_url(match):
        url = match.group(1)
        local_path = download_image(url)
        return local_path

    return re.sub(wp_image_pattern, replace_url, content)


def clean_html(html_content):
    """Convert HTML to clean markdown."""
    if not html_content:
        return ""
    # Decode HTML entities
    content = html.unescape(html_content)
    # Convert to markdown
    content = md(content, heading_style="ATX", bullets="-")
    # Clean up extra whitespace
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def clean_title(title):
    """Clean HTML entities from title."""
    return html.unescape(title)


def slugify(text):
    """Convert text to URL-friendly slug."""
    text = text.lower()
    text = re.sub(r"[àáâãäå]", "a", text)
    text = re.sub(r"[èéêë]", "e", text)
    text = re.sub(r"[ìíîï]", "i", text)
    text = re.sub(r"[òóôõö]", "o", text)
    text = re.sub(r"[ùúûü]", "u", text)
    text = re.sub(r"[ç]", "c", text)
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = re.sub(r"-+", "-", text)
    return text.strip("-")


def fetch_posts():
    """Fetch all posts from WordPress."""
    posts = []
    page = 1
    while True:
        response = requests.get(
            f"{WORDPRESS_URL}/wp-json/wp/v2/posts",
            params={"per_page": 100, "page": page},
            headers=HEADERS,
        )
        if response.status_code != 200:
            break
        data = response.json()
        if not data:
            break
        posts.extend(data)
        page += 1
    return posts


def fetch_pages():
    """Fetch all pages from WordPress."""
    pages = []
    page = 1
    while True:
        response = requests.get(
            f"{WORDPRESS_URL}/wp-json/wp/v2/pages",
            params={"per_page": 100, "page": page},
            headers=HEADERS,
        )
        if response.status_code != 200:
            break
        data = response.json()
        if not data:
            break
        pages.extend(data)
        page += 1
    return pages


def fetch_categories():
    """Fetch all categories from WordPress."""
    response = requests.get(
        f"{WORDPRESS_URL}/wp-json/wp/v2/categories",
        params={"per_page": 100},
        headers=HEADERS,
    )
    if response.status_code == 200:
        return {cat["id"]: cat["name"] for cat in response.json()}
    return {}


def save_post_as_noticia(post, categories):
    """Save a WordPress post as an Astro noticia."""
    title = clean_title(post["title"]["rendered"])
    content = clean_html(post["content"]["rendered"])
    date = datetime.fromisoformat(post["date"].replace("Z", "+00:00"))
    excerpt = clean_html(post.get("excerpt", {}).get("rendered", ""))

    # Get featured image if exists
    hero_image = ""
    if post.get("featured_media"):
        media_response = requests.get(
            f"{WORDPRESS_URL}/wp-json/wp/v2/media/{post['featured_media']}",
            headers=HEADERS,
        )
        if media_response.status_code == 200:
            hero_image = media_response.json().get("source_url", "")

    # Download hero image
    if hero_image:
        hero_image = download_image(hero_image)

    # Download all images in content
    content = replace_image_urls(content)

    # Create filename
    date_prefix = date.strftime("%Y-%m-%d")
    slug = slugify(title)[:50]
    filename = f"{date_prefix}-{slug}.md"

    # Create frontmatter
    frontmatter = f"""---
title: "{title}"
description: "{excerpt[:200].replace('"', "'")}"
pubDate: {date.isoformat()}
heroImage: "{hero_image}"
---

{content}
"""

    # Save file
    output_dir = os.path.join(ASTRO_CONTENT_DIR, "noticies")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, filename)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(frontmatter)

    print(f"  Created: noticies/{filename}")
    return filename


def save_page(page, content_type, filename, extra_frontmatter=None):
    """Save a WordPress page as an Astro content file."""
    title = clean_title(page["title"]["rendered"])
    content = clean_html(page["content"]["rendered"])

    # Download all images in content
    content = replace_image_urls(content)

    # Build frontmatter
    fm_parts = [f'title: "{title}"', f'description: "{title}"']

    if extra_frontmatter:
        for key, value in extra_frontmatter.items():
            if isinstance(value, str):
                fm_parts.append(f'{key}: "{value}"')
            else:
                fm_parts.append(f"{key}: {value}")

    frontmatter = "---\n" + "\n".join(fm_parts) + "\n---\n\n" + content + "\n"

    # Save file
    output_dir = os.path.join(ASTRO_CONTENT_DIR, content_type)
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"{filename}.md")

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(frontmatter)

    print(f"  Created: {content_type}/{filename}.md")
    return filename


def main():
    print("=" * 60)
    print("WordPress to Astro Migration (with images)")
    print("=" * 60)
    print(f"Source: {WORDPRESS_URL}")
    print(f"Content: {ASTRO_CONTENT_DIR}")
    print(f"Images: {IMAGES_DIR}")
    print()

    # Create images directory
    os.makedirs(IMAGES_DIR, exist_ok=True)

    # Fetch categories
    print("Fetching categories...")
    categories = fetch_categories()
    print(f"  Found {len(categories)} categories")

    # Fetch and migrate posts
    print("\nFetching posts...")
    posts = fetch_posts()
    print(f"  Found {len(posts)} posts")

    print("\nMigrating posts to noticies...")
    for post in posts:
        save_post_as_noticia(post, categories)

    # Fetch and migrate pages
    print("\nFetching pages...")
    pages = fetch_pages()
    print(f"  Found {len(pages)} pages")

    print("\nMigrating pages...")
    pages_by_slug = {p["slug"]: p for p in pages}

    for wp_slug, (content_type, filename, extra_fm) in PAGE_MAPPING.items():
        if wp_slug in pages_by_slug:
            save_page(pages_by_slug[wp_slug], content_type, filename, extra_fm)
        else:
            print(f"  Warning: Page '{wp_slug}' not found in WordPress")

    print("\n" + "=" * 60)
    print(f"Migration complete!")
    print(f"Downloaded {len(downloaded_images)} images to {IMAGES_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
