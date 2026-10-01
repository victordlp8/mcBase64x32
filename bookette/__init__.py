"""bookette package encoding for Minecraft books."""

from importlib.metadata import version
from .main import encode, decode, encode_pages, decode_pages, MAX_BYTES_PER_PAGE

__version__ = version("bookette")

__all__ = ["encode", "decode", "encode_pages", "decode_pages", "MAX_BYTES_PER_PAGE"]