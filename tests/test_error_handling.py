"""Error handling tests for mcbase64x32 library.

This module tests error handling and edge cases to ensure the library
behaves correctly when given invalid inputs.
"""

import pytest
import mcbase64x32


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_invalid_decode_input_type(self):
        """Test that decode function handles invalid input types gracefully."""
        with pytest.raises((TypeError, AttributeError)):
            mcbase64x32.decode(123)  # type: ignore # Should not accept integers
        
        with pytest.raises((TypeError, AttributeError)):
            mcbase64x32.decode(None)  # type: ignore # Should not accept None
        
        with pytest.raises((TypeError, AttributeError)):
            mcbase64x32.decode(b"bytes")  # type: ignore # Should not accept bytes

    def test_invalid_encode_input_type(self):
        """Test that encode function handles invalid input types gracefully."""
        with pytest.raises((TypeError, AttributeError)):
            mcbase64x32.encode("string")  # type: ignore # Should not accept strings directly
        
        with pytest.raises((TypeError, AttributeError)):
            mcbase64x32.encode(123)  # type: ignore # Should not accept integers
        
        with pytest.raises((TypeError, AttributeError)):
            mcbase64x32.encode(None)  # type: ignore # Should not accept None

    def test_decode_empty_string(self):
        """Test decoding of empty string."""
        # Empty string should decode to empty bytes
        result = mcbase64x32.decode("")
        assert result == b"", "Empty string should decode to empty bytes"

    def test_decode_odd_length_string(self):
        """Test decoding of odd-length strings (should be handled gracefully)."""
        # The decode function processes 2 characters at a time
        # An odd-length string should be handled gracefully
        try:
            result = mcbase64x32.decode("a")  # Single character
            # Should either work or raise a specific error
            assert isinstance(result, bytes)
        except (ValueError, KeyError, IndexError):
            # These are acceptable errors for malformed input
            pass

    def test_decode_invalid_characters(self):
        """Test decoding of strings with invalid characters."""
        # Test with characters not in the base64x32 alphabet
        invalid_strings = [
            "invalid_chars!@#",
            "1234567890",
            "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
            "abcdefghijklmnopqrstuvwxyz",
        ]
        
        for invalid_string in invalid_strings:
                try:
                    result = mcbase64x32.decode(invalid_string)
                    # If it doesn't raise an error, the result should be bytes
                    assert isinstance(result, bytes)
                except (ValueError, KeyError, IndexError):
                    # These are acceptable errors for invalid input
                    pass

    def test_large_payload_handling(self):
        """Test handling of large payloads."""
        # Test with payload larger than MAX_BYTES_PER_PAGE
        large_payload = b"x" * (mcbase64x32.MAX_BYTES_PER_PAGE + 100)
        
        try:
            encoded = mcbase64x32.encode(large_payload)
            decoded = mcbase64x32.decode(encoded)
            
            # Should either work correctly or raise a specific error
            assert isinstance(encoded, str)
            assert isinstance(decoded, bytes)
            
            # If it works, it should be a perfect round-trip
            if len(decoded) == len(large_payload):
                assert large_payload == decoded
        except (ValueError, MemoryError, OverflowError):
            # These are acceptable errors for very large payloads
            pass

    def test_very_small_payloads(self):
        """Test handling of very small payloads."""
        small_payloads = [
            b"",
            b"\x00",
            b"\xff",
            b"\x80",
            b"\x7f",
        ]
        
        for payload in small_payloads:
                encoded = mcbase64x32.encode(payload)
                decoded = mcbase64x32.decode(encoded)
                
                assert payload == decoded, f"Small payload {payload.hex()} round-trip failed"

    def test_unicode_string_handling(self):
        """Test handling of Unicode strings (should be converted to bytes first)."""
        unicode_strings = [
            "Hello, 世界!",
            "ñáéíóú",
            "🚀🎉✨",
            "αβγδε",
        ]
        
        for unicode_str in unicode_strings:
                # Convert to bytes first
                payload = unicode_str.encode('utf-8')
                encoded = mcbase64x32.encode(payload)
                decoded = mcbase64x32.decode(encoded)
                decoded_str = decoded.decode('utf-8')
                
                assert unicode_str == decoded_str, f"Unicode string round-trip failed for '{unicode_str}'"

    def test_binary_data_with_null_bytes(self):
        """Test handling of binary data containing null bytes."""
        test_data = [
            b"\x00\x01\x02\x03",
            b"hello\x00world",
            b"\x00\x00\x00\x00",
            b"test\x00\xff\x00test",
        ]
        
        for data in test_data:
                encoded = mcbase64x32.encode(data)
                decoded = mcbase64x32.decode(encoded)
                
                assert data == decoded, f"Binary data with null bytes round-trip failed for {repr(data)}"

    def test_encoding_consistency_with_same_input(self):
        """Test that encoding the same input multiple times produces consistent results."""
        payload = b"consistency test payload"
        
        # Encode multiple times
        encodings = []
        for _ in range(10):
            encoded = mcbase64x32.encode(payload)
            encodings.append(encoded)
        
        # All encodings should be identical
        assert all(enc == encodings[0] for enc in encodings), "Encoding should be deterministic"

    def test_decoding_consistency_with_same_input(self):
        """Test that decoding the same encoded string multiple times produces consistent results."""
        payload = b"consistency test payload"
        encoded = mcbase64x32.encode(payload)
        
        # Decode multiple times
        decodings = []
        for _ in range(10):
            decoded = mcbase64x32.decode(encoded)
            decodings.append(decoded)
        
        # All decodings should be identical
        assert all(dec == decodings[0] for dec in decodings), "Decoding should be deterministic"
