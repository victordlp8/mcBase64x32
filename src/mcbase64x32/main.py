import json


with open("src/mcbase64x32/utils/baseList.json", "r", encoding="utf-8") as f:
    base_dict = json.load(f)


def encode_string_binary(text):
    """Encodes a string by converting it to binary and grouping it into 11-bit blocks"""
    # Convert text to binary
    binary_str = "".join(format(ord(char), "08b") for char in text)

    # Pad with zeros if not a multiple of 11
    padding = (11 - (len(binary_str) % 11)) % 11
    binary_str += "0" * padding

    # Group into 11-bit blocks and convert to characters
    encoded = ""
    for i in range(0, len(binary_str), 11):
        chunk = binary_str[i : i + 11]
        decimal_value = int(chunk, 2)  # Convert from binary to decimal
        encoded += base_dict["encode"][str(decimal_value)]

    return encoded


def decode_string_binary(encoded_text):
    """Decodes a string that was encoded with the 11-bit binary method"""
    # Convert each pair of encoded characters back to their decimal value
    binary_str = ""
    i = 0
    while i < len(encoded_text):
        # Take 2 characters (each encoding uses 2 characters)
        char_pair = encoded_text[i : i + 2]
        if char_pair in base_dict["decode"]:
            decimal_value = base_dict["decode"][char_pair]
            binary_chunk = format(
                decimal_value, "011b"
            )  # 11 bits con ceros a la izquierda
            binary_str += binary_chunk
        i += 2

    # Convert back to characters (8-bit groups)
    decoded = ""
    for i in range(0, len(binary_str), 8):
        byte_chunk = binary_str[i : i + 8]
        if len(byte_chunk) == 8:  # Only process complete blocks
            decoded += chr(int(byte_chunk, 2))

    return decoded


def main():
    message = "Hello from mcbase64x32!"
    encoded = encode_string_binary(message)
    decoded = decode_string_binary(encoded)

    print(f"{message} -> {encoded}    -> {decoded}")
    print(f"Compression: {len(message)} chars -> {len(encoded)} chars")


if __name__ == "__main__":
    main()
