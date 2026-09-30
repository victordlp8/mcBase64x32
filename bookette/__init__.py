"""bookette package encoding for Minecraft books."""

from importlib.metadata import version
from .main import encode, decode

__version__ = version("bookette")

__all__ = ["encode", "decode"]