"""
Helper utility functions.
"""
import re
import html
from typing import List
from bs4 import BeautifulSoup


def sanitize_filename(filename: str) -> str:
    """Sanitize filename for safe file system usage."""
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '', filename)
    # Replace spaces with underscores
    filename = filename.replace(' ', '_')
    # Limit length
    if len(filename) > 200:
        filename = filename[:200]
    return filename


def extract_images_from_html(html_content: str) -> List[str]:
    """
    Extract all image URLs from HTML content.

    Args:
        html_content: HTML string

    Returns:
        List of image URLs
    """
    if not html_content:
        return []

    soup = BeautifulSoup(html_content, 'html.parser')
    img_urls = []

    for img in soup.find_all('img'):
        src = img.get('src')
        if src:
            # Handle relative URLs
            if src.startswith('//'):
                src = 'https:' + src
            elif src.startswith('/'):
                src = 'https://math.stackexchange.com' + src  # Default to math SE
            img_urls.append(src)

    return img_urls


def strip_html_tags(html_content: str) -> str:
    """
    Strip HTML tags and decode HTML entities.

    Args:
        html_content: HTML string

    Returns:
        Plain text
    """
    if not html_content:
        return ''

    soup = BeautifulSoup(html_content, 'html.parser')
    text = soup.get_text()
    # Decode HTML entities
    text = html.unescape(text)
    return text


def merge_text_with_images(html_content: str, image_ocr_texts: dict) -> str:
    """
    Merge HTML content with OCR text from images.

    Args:
        html_content: Original HTML
        image_ocr_texts: Dict mapping image URLs to OCR text

    Returns:
        Merged text content
    """
    soup = BeautifulSoup(html_content, 'html.parser')

    for img in soup.find_all('img'):
        src = img.get('src', '')
        if src in image_ocr_texts:
            # Replace image with OCR text
            ocr_text = image_ocr_texts[src]
            new_tag = soup.new_tag('span')
            new_tag.string = f' [Image: {ocr_text}] '
            img.replace_with(new_tag)

    return soup.get_text()
