"""mcbase64x32 package - High-performance base64x32 encoding for Minecraft books.

This package provides optimized encoding/decoding using numpy vectorized operations
for maximum performance when storing data in Minecraft books.
"""

__version__ = "0.1.0"

from .main import MAX_BYTES_PER_PAGE
from .mcbase64x32 import encode, decode


__all__ = ["MAX_BYTES_PER_PAGE", "encode", "decode"]
