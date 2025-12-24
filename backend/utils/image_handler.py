"""
Image handler for downloading and processing images.
"""
import os
import hashlib
import requests
from pathlib import Path
from typing import Optional, Tuple
from PIL import Image
import io


class ImageHandler:
    """Handle image downloading and processing."""

    def __init__(self, storage_dir: str = None):
        """
        Initialize image handler.

        Args:
            storage_dir: Directory to store downloaded images
        """
        if storage_dir is None:
            storage_dir = '/datadisk/Web2Lean/data/images'
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def download_image(self, url: str) -> Optional[bytes]:
        """
        Download image from URL.

        Args:
            url: Image URL

        Returns:
            Image binary data or None if failed
        """
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            return response.content
        except Exception as e:
            print(f"Failed to download image from {url}: {e}")
            return None

    def save_image(self, image_data: bytes, filename: str) -> str:
        """
        Save image to storage directory.

        Args:
            image_data: Image binary data
            filename: Filename to use

        Returns:
            Full path to saved image
        """
        filepath = self.storage_dir / filename
        with open(filepath, 'wb') as f:
            f.write(image_data)
        return str(filepath)

    def get_image_info(self, image_data: bytes) -> Tuple[str, int]:
        """
        Get image information (mime type and size).

        Args:
            image_data: Image binary data

        Returns:
            Tuple of (mime_type, file_size)
        """
        try:
            img = Image.open(io.BytesIO(image_data))
            format_map = {
                'JPEG': 'image/jpeg',
                'PNG': 'image/png',
                'GIF': 'image/gif',
                'WEBP': 'image/webp',
                'SVG': 'image/svg+xml',
            }
            mime_type = format_map.get(img.format, 'application/octet-stream')
            return mime_type, len(image_data)
        except Exception:
            return 'application/octet-stream', len(image_data)

    def generate_filename(self, url: str) -> str:
        """
        Generate unique filename from URL.

        Args:
            url: Image URL

        Returns:
            Unique filename
        """
        # Hash URL for unique filename
        url_hash = hashlib.md5(url.encode()).hexdigest()[:12]

        # Try to get extension from URL
        ext = '.jpg'
        if '.' in url.split('/')[-1]:
            potential_ext = '.' + url.split('.')[-1].split('?')[0].lower()
            if potential_ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
                ext = potential_ext

        return f"{url_hash}{ext}"

    def resize_image(self, image_data: bytes, max_size: Tuple[int, int] = (1024, 1024)) -> bytes:
        """
        Resize image if it's larger than max_size.

        Args:
            image_data: Image binary data
            max_size: Maximum (width, height)

        Returns:
            Resized image data
        """
        try:
            img = Image.open(io.BytesIO(image_data))

            # Check if resize needed
            if img.width <= max_size[0] and img.height <= max_size[1]:
                return image_data

            # Calculate new size maintaining aspect ratio
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Save to bytes
            output = io.BytesIO()
            img.save(output, format=img.format or 'JPEG', quality=85)
            return output.getvalue()
        except Exception:
            return image_data

    def process_image(self, url: str, resize: bool = True) -> Optional[Tuple[bytes, str, int]]:
        """
        Download and process an image.

        Args:
            url: Image URL
            resize: Whether to resize large images

        Returns:
            Tuple of (image_data, mime_type, file_size) or None
        """
        image_data = self.download_image(url)
        if not image_data:
            return None

        if resize:
            image_data = self.resize_image(image_data)

        mime_type, file_size = self.get_image_info(image_data)
        return image_data, mime_type, file_size
