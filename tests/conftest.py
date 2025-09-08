"""Pytest configuration and fixtures for mcbase64x32 tests."""

import pytest
import random
from typing import Generator


@pytest.fixture(scope="session")
def random_seed() -> int:
    """Set a fixed random seed for reproducible tests."""
    seed = 42
    random.seed(seed)
    return seed


@pytest.fixture
def sample_binary_data() -> list[bytes]:
    """Provide sample binary data for testing."""
    return [
        b"",
        b"\x00",
        b"\xff",
        b"\x80",
        b"\x7f",
        b"\x00\x01\x02\x03",
        b"\xff\xfe\xfd\xfc",
        b"Hello, World!",
        b"\x15\xfa\xce\x70\x00\x00\x01",
        b"\x78\x9c\x0b\x49\x2d\x2e\x51\x28",
    ]


@pytest.fixture
def high_bit_bytes() -> list[bytes]:
    """Provide high-bit bytes (0x80-0xFF) for testing."""
    return [bytes([i]) for i in range(128, 256)]


@pytest.fixture
def all_byte_values() -> list[bytes]:
    """Provide all possible byte values (0x00-0xFF) for testing."""
    return [bytes([i]) for i in range(256)]


@pytest.fixture
def problematic_payloads() -> list[bytes]:
    """Provide payloads that are known to cause issues."""
    return [
        bytes.fromhex("15face70000001789c0b492d2e5128ce4dccc95148cbcc495548cb2f5248494d2a4d4fcfcc4be7e50200b5560ae4"),
        bytes.fromhex("15face70"),
        bytes.fromhex("fa"),
        bytes.fromhex("ce"),
        bytes.fromhex("cc"),
    ]


@pytest.fixture
def metadata_like_patterns() -> list[bytes]:
    """Provide metadata-like patterns for testing."""
    return [
        b"\x15\xfa\xce\x70\x00\x00\x01",
        b"\x78\x9c\x0b\x49\x2d\x2e\x51\x28",
        b"\x00\x01\x02\x03\x80\x81\x82\x83",
        b"\xff\xfe\xfd\xfc\x7f\x7e\x7d\x7c",
        b"metadata\x00\x01\x02\x03\x04\x05",
        b"\x15\xfa\xce\x70" + b"data" + b"\x00\x00\x01",
    ]


@pytest.fixture
def random_payload_generator(random_seed: int) -> Generator[bytes, None, None]:
    """Generate random payloads for testing."""
    random.seed(random_seed)
    
    def generate_payload(size: int) -> bytes:
        return bytes([random.randint(0, 255) for _ in range(size)])
    
    return generate_payload


@pytest.fixture(autouse=True)
def reset_random_seed():
    """Reset random seed before each test."""
    random.seed(42)
    yield
    random.seed(42)
