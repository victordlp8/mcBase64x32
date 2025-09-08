"""Comprehensive round-trip tests for mcbase64x32 library.

This module tests the core functionality of encoding and decoding binary data
to ensure no data corruption occurs during round-trip operations.
"""

import pytest
import random
from typing import List, Dict, Any

import mcbase64x32


class TestRoundTrip:
    """Test round-trip encoding/decoding functionality."""

    def test_known_failure_case(self):
        """Test the specific payload that was reported to fail."""
        # Original failing case from bug report
        payload = bytes.fromhex("15face70000001789c0b492d2e5128ce4dccc95148cbcc495548cb2f5248494d2a4d4fcfcc4be7e50200b5560ae4")
        
        encoded = mcbase64x32.encode(payload)
        decoded = mcbase64x32.decode(encoded)
        
        assert payload == decoded, (
            f"Round-trip failed for known failure case:\n"
            f"Original: {payload.hex()}\n"
            f"Decoded:  {decoded.hex()}\n"
            f"Encoded:  {repr(encoded)}"
        )

    def test_simplified_failure_cases(self):
        """Test simplified cases to isolate the problem."""
        test_cases = [
            "15face70",  # Just the problematic bytes
            "fa",        # Single problematic byte
            "ce",        # Another problematic byte
            "cc",        # Another problematic byte
        ]
        
        for hex_payload in test_cases:
            payload = bytes.fromhex(hex_payload)
            encoded = mcbase64x32.encode(payload)
            decoded = mcbase64x32.decode(encoded)
            
            assert payload == decoded, (
                    f"Round-trip failed for {hex_payload}:\n"
                    f"Original: {payload.hex()}\n"
                    f"Decoded:  {decoded.hex()}\n"
                    f"Encoded:  {repr(encoded)}"
                )

    def test_edge_cases(self):
        """Test edge cases with special byte values."""
        test_cases = [
            "00",        # Null byte
            "ff",        # Max byte
            "8090a0b0c0d0e0f0",  # Various high-bit bytes
            "7f",        # Max 7-bit byte
            "80",        # First high-bit byte
        ]
        
        for hex_payload in test_cases:
            payload = bytes.fromhex(hex_payload)
            encoded = mcbase64x32.encode(payload)
            decoded = mcbase64x32.decode(encoded)
            
            assert payload == decoded, (
                    f"Round-trip failed for edge case {hex_payload}:\n"
                    f"Original: {payload.hex()}\n"
                    f"Decoded:  {decoded.hex()}\n"
                    f"Encoded:  {repr(encoded)}"
                )

    def test_all_high_bit_bytes(self):
        """Test all high-bit bytes (0x80-0xFF) individually."""
        failures = []
        
        for byte_val in range(128, 256):  # Test all high-bit bytes
            payload = bytes([byte_val])
            
            try:
                encoded = mcbase64x32.encode(payload)
                decoded = mcbase64x32.decode(encoded)
                
                if payload != decoded:
                    failures.append({
                        'byte': f"0x{byte_val:02x}",
                        'original': payload.hex(),
                        'decoded': decoded.hex(),
                        'encoded': repr(encoded)
                    })
            except Exception as e:
                failures.append({
                    'byte': f"0x{byte_val:02x}",
                    'error': str(e)
                })
        
        assert len(failures) == 0, (
            f"High-bit byte tests failed for {len(failures)} bytes:\n" +
            "\n".join(f"Byte {f['byte']}: {f}" for f in failures[:10]) +
            (f"\n... and {len(failures) - 10} more failures" if len(failures) > 10 else "")
        )

    def test_all_byte_values(self):
        """Test all possible byte values (0x00-0xFF)."""
        failures = []
        
        for byte_val in range(256):
            payload = bytes([byte_val])
            
            try:
                encoded = mcbase64x32.encode(payload)
                decoded = mcbase64x32.decode(encoded)
                
                if payload != decoded:
                    failures.append({
                        'byte': f"0x{byte_val:02x}",
                        'original': payload.hex(),
                        'decoded': decoded.hex(),
                        'encoded': repr(encoded)
                    })
            except Exception as e:
                failures.append({
                    'byte': f"0x{byte_val:02x}",
                    'error': str(e)
                })
        
        assert len(failures) == 0, (
            f"All byte values test failed for {len(failures)} bytes:\n" +
            "\n".join(f"Byte {f['byte']}: {f}" for f in failures[:10]) +
            (f"\n... and {len(failures) - 10} more failures" if len(failures) > 10 else "")
        )

    @pytest.mark.parametrize("test_size", [1, 7, 16, 32, 64, 128, 256, 512, 1024])
    def test_random_binary_payloads(self, test_size: int):
        """Test random binary payloads of various sizes."""
        random.seed(42)  # Fixed seed for reproducible tests
        failures = []
        
        for test_num in range(100):  # 100 random tests per size
            # Generate random binary data
            payload = bytes([random.randint(0, 255) for _ in range(test_size)])
            
            try:
                encoded = mcbase64x32.encode(payload)
                decoded = mcbase64x32.decode(encoded)
                
                if payload != decoded:
                    failures.append({
                        'size': test_size,
                        'test_num': test_num,
                        'original': payload.hex(),
                        'decoded': decoded.hex(),
                        'encoded_text': repr(encoded)
                    })
            except Exception as e:
                failures.append({
                    'size': test_size,
                    'test_num': test_num,
                    'original': payload.hex(),
                    'error': str(e)
                })
        
        assert len(failures) == 0, (
            f"Random binary payload tests failed for size {test_size}: {len(failures)} failures\n" +
            "\n".join(f"Test {f['test_num']}: {f}" for f in failures[:5]) +
            (f"\n... and {len(failures) - 5} more failures" if len(failures) > 5 else "")
        )

    def test_empty_payload(self):
        """Test encoding/decoding of empty payload."""
        payload = b""
        encoded = mcbase64x32.encode(payload)
        decoded = mcbase64x32.decode(encoded)
        
        assert payload == decoded, "Empty payload round-trip failed"

    def test_single_byte_payloads(self):
        """Test all single-byte payloads."""
        for byte_val in range(256):
                payload = bytes([byte_val])
                encoded = mcbase64x32.encode(payload)
                decoded = mcbase64x32.decode(encoded)
                
                assert payload == decoded, (
                    f"Single byte {byte_val:02x} round-trip failed:\n"
                    f"Original: {payload.hex()}\n"
                    f"Decoded:  {decoded.hex()}\n"
                    f"Encoded:  {repr(encoded)}"
                )

    def test_metadata_like_patterns(self):
        """Test patterns similar to metadata (hash + small integers + binary data)."""
        test_patterns = [
            # Hash-like patterns
            b"\x15\xfa\xce\x70\x00\x00\x01",
            b"\x78\x9c\x0b\x49\x2d\x2e\x51\x28",
            # Mixed patterns
            b"\x00\x01\x02\x03\x80\x81\x82\x83",
            b"\xff\xfe\xfd\xfc\x7f\x7e\x7d\x7c",
            # Real-world like patterns
            b"metadata\x00\x01\x02\x03\x04\x05",
            b"\x15\xfa\xce\x70" + b"data" + b"\x00\x00\x01",
        ]
        
        for i, payload in enumerate(test_patterns):
                encoded = mcbase64x32.encode(payload)
                decoded = mcbase64x32.decode(encoded)
                
                assert payload == decoded, (
                    f"Metadata-like pattern {i} round-trip failed:\n"
                    f"Original: {payload.hex()}\n"
                    f"Decoded:  {decoded.hex()}\n"
                    f"Encoded:  {repr(encoded)}"
                )

    def test_utf8_corruption_detection(self):
        """Test specific UTF-8 corruption patterns mentioned in bug report."""
        # These are the specific corruption patterns mentioned in the bug report
        corruption_tests = [
            ("fa", "c3ba"),  # 0xFA -> UTF-8 encoding
            ("ce", "c38e"),  # 0xCE -> UTF-8 encoding  
            ("cc", "c38c"),  # 0xCC -> UTF-8 encoding
        ]
        
        for original_hex, corrupted_hex in corruption_tests:
                payload = bytes.fromhex(original_hex)
                encoded = mcbase64x32.encode(payload)
                decoded = mcbase64x32.decode(encoded)
                
                # The decoded should NOT contain the corrupted UTF-8 patterns
                decoded_hex = decoded.hex()
                assert corrupted_hex not in decoded_hex, (
                    f"UTF-8 corruption detected for {original_hex}:\n"
                    f"Expected: {original_hex}\n"
                    f"Got:      {decoded_hex}\n"
                    f"Contains corrupted pattern: {corrupted_hex}"
                )
                
                # And it should match the original
                assert payload == decoded, (
                    f"Round-trip failed for {original_hex}:\n"
                    f"Original: {payload.hex()}\n"
                    f"Decoded:  {decoded.hex()}\n"
                    f"Encoded:  {repr(encoded)}"
                )
