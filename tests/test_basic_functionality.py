"""Basic functionality tests for mcbase64x32 library.

This module tests the basic encoding/decoding functionality and edge cases
to ensure the library works correctly for various input types.
"""

import pytest
import mcbase64x32


class TestBasicFunctionality:
    """Test basic encoding/decoding functionality."""

    def test_text_encoding_decoding(self):
        """Test encoding and decoding of text strings."""
        test_strings = [
            "Hello, World!",
            "mcbase64x32",
            "Test with special chars: !@#$%^&*()",
            "Unicode: ñáéíóú",
            "Numbers: 1234567890",
            "",
            "a",
            "ab",
            "abc",
        ]
        
        for text in test_strings:
                payload = text.encode('utf-8')
                encoded = mcbase64x32.encode(payload)
                decoded = mcbase64x32.decode(encoded)
                decoded_text = decoded.decode('utf-8')
                
                assert text == decoded_text, (
                    f"Text round-trip failed for '{text}':\n"
                    f"Original: {text}\n"
                    f"Decoded:  {decoded_text}\n"
                    f"Encoded:  {repr(encoded)}"
                )

    def test_binary_data_encoding_decoding(self):
        """Test encoding and decoding of binary data."""
        test_data = [
            b"Hello, World!",
            b"\x00\x01\x02\x03",
            b"\xff\xfe\xfd\xfc",
            b"",
            b"\x00",
            b"\xff",
            b"\x80",
            b"\x7f",
        ]
        
        for data in test_data:
                encoded = mcbase64x32.encode(data)
                decoded = mcbase64x32.decode(encoded)
                
                assert data == decoded, (
                    f"Binary data round-trip failed for {data.hex()}:\n"
                    f"Original: {data.hex()}\n"
                    f"Decoded:  {decoded.hex()}\n"
                    f"Encoded:  {repr(encoded)}"
                )

    def test_max_bytes_per_page_constant(self):
        """Test that MAX_BYTES_PER_PAGE constant is accessible."""
        assert hasattr(mcbase64x32, 'MAX_BYTES_PER_PAGE')
        assert isinstance(mcbase64x32.MAX_BYTES_PER_PAGE, int)
        assert mcbase64x32.MAX_BYTES_PER_PAGE > 0

    def test_encode_function_signature(self):
        """Test that encode function accepts bytes and returns string."""
        payload = b"test"
        result = mcbase64x32.encode(payload)
        
        assert isinstance(result, str), f"encode() should return str, got {type(result)}"

    def test_decode_function_signature(self):
        """Test that decode function accepts string and returns bytes."""
        encoded = mcbase64x32.encode(b"test")
        result = mcbase64x32.decode(encoded)
        
        assert isinstance(result, bytes), f"decode() should return bytes, got {type(result)}"

    def test_empty_input_handling(self):
        """Test handling of empty inputs."""
        # Empty bytes
        empty_bytes = b""
        encoded = mcbase64x32.encode(empty_bytes)
        decoded = mcbase64x32.decode(encoded)
        assert empty_bytes == decoded

    def test_single_character_encoding(self):
        """Test encoding of single characters."""
        for i in range(256):
            char = bytes([i])
            encoded = mcbase64x32.encode(char)
            decoded = mcbase64x32.decode(encoded)
            assert char == decoded, f"Single character {i:02x} encoding failed"

    def test_encoding_idempotency(self):
        """Test that encoding the same data multiple times produces the same result."""
        payload = b"test payload"
        
        encoded1 = mcbase64x32.encode(payload)
        encoded2 = mcbase64x32.encode(payload)
        
        assert encoded1 == encoded2, "Encoding should be idempotent"

    def test_decoding_idempotency(self):
        """Test that decoding the same encoded string multiple times produces the same result."""
        payload = b"test payload"
        encoded = mcbase64x32.encode(payload)
        
        decoded1 = mcbase64x32.decode(encoded)
        decoded2 = mcbase64x32.decode(encoded)
        
        assert decoded1 == decoded2, "Decoding should be idempotent"

    def test_round_trip_consistency(self):
        """Test that multiple round-trips produce consistent results."""
        payload = b"test payload for multiple round-trips"
        
        # Multiple encode/decode cycles
        current = payload
        for i in range(5):
            encoded = mcbase64x32.encode(current)
            current = mcbase64x32.decode(encoded)
        
        assert payload == current, f"Multiple round-trips failed after 5 cycles"

    def test_encoding_length_consistency(self):
        """Test that encoding produces consistent length for same input."""
        payload = b"consistent length test"
        
        lengths = []
        for _ in range(10):
            encoded = mcbase64x32.encode(payload)
            lengths.append(len(encoded))
        
        assert all(length == lengths[0] for length in lengths), "Encoding length should be consistent"

    def test_high_bit_byte_sequences(self):
        """Test sequences of high-bit bytes."""
        test_sequences = [
            b"\x80\x81\x82\x83",
            b"\x90\x91\x92\x93",
            b"\xa0\xa1\xa2\xa3",
            b"\xb0\xb1\xb2\xb3",
            b"\xc0\xc1\xc2\xc3",
            b"\xd0\xd1\xd2\xd3",
            b"\xe0\xe1\xe2\xe3",
            b"\xf0\xf1\xf2\xf3",
        ]
        
        for sequence in test_sequences:
                encoded = mcbase64x32.encode(sequence)
                decoded = mcbase64x32.decode(encoded)
                
                assert sequence == decoded, (
                    f"High-bit sequence round-trip failed for {sequence.hex()}:\n"
                    f"Original: {sequence.hex()}\n"
                    f"Decoded:  {decoded.hex()}\n"
                    f"Encoded:  {repr(encoded)}"
                )
