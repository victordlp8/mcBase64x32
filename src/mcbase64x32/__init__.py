"""mcbase64x32 package - High-performance base64x32 encoding for Minecraft books.

This package provides optimized encoding/decoding using numpy vectorized operations
for maximum performance when storing data in Minecraft books.
"""

__version__ = "0.1.0"

from .main import encode, decode, MAX_BYTES_PER_PAGE

__all__ = ["encode", "decode", "MAX_BYTES_PER_PAGE"]
