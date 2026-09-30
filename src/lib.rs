use std::collections::HashMap;

use bitstream_io::{BigEndian, BitRead, BitReader, BitWrite, BitWriter};
use lazy_static::lazy_static;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;

const WIDTH_1_CHARS: &str = include_str!("1_width.txt");
const WIDTH_2_CHARS: &str = include_str!("2_width.txt");
const WIDTH_1_COUNT: u64 = 107;
const WIDTH_2_COUNT: u64 = 210;
const BLOCK_BITS: u32 = 63;
const WIDTH_1_PAIRS: u64 = WIDTH_1_COUNT * WIDTH_1_COUNT;
const WIDTH_1_2_PAIRS: u64 = WIDTH_1_COUNT * WIDTH_2_COUNT;
const PAIR_RADIX: u64 = WIDTH_1_PAIRS + 2 * WIDTH_1_2_PAIRS;

lazy_static! {
    static ref WIDTH_1: Vec<char> = WIDTH_1_CHARS.chars().collect();
    static ref WIDTH_2: Vec<char> = WIDTH_2_CHARS.chars().collect();
    static ref DECODE_CHARS: HashMap<char, (u8, u16)> = {
        let mut chars = HashMap::new();
        for (i, ch) in WIDTH_1.iter().enumerate() {
            chars.insert(*ch, (1, i as u16));
        }
        for (i, ch) in WIDTH_2.iter().enumerate() {
            chars.insert(*ch, (2, i as u16));
        }
        chars
    };
}

fn encode_pair(value: u16, output: &mut String) {
    let value = u64::from(value);
    if value < WIDTH_1_PAIRS {
        output.push(WIDTH_1[(value / WIDTH_1_COUNT) as usize]);
        output.push(WIDTH_1[(value % WIDTH_1_COUNT) as usize]);
    } else if value < WIDTH_1_PAIRS + WIDTH_1_2_PAIRS {
        let value = value - WIDTH_1_PAIRS;
        output.push(WIDTH_1[(value / WIDTH_2_COUNT) as usize]);
        output.push(WIDTH_2[(value % WIDTH_2_COUNT) as usize]);
    } else {
        let value = value - WIDTH_1_PAIRS - WIDTH_1_2_PAIRS;
        output.push(WIDTH_2[(value / WIDTH_1_COUNT) as usize]);
        output.push(WIDTH_1[(value % WIDTH_1_COUNT) as usize]);
    }
}

fn encode_block(mut value: u64, output: &mut String) {
    let mut pairs = [0u16; 4];
    for pair in pairs.iter_mut().rev() {
        *pair = (value % PAIR_RADIX) as u16;
        value /= PAIR_RADIX;
    }
    debug_assert_eq!(value, 0);
    for pair in pairs {
        encode_pair(pair, output);
    }
}

fn decode_pair(first: char, second: char) -> Option<u16> {
    let &(first_width, first_index) = DECODE_CHARS.get(&first)?;
    let &(second_width, second_index) = DECODE_CHARS.get(&second)?;
    let value = match (first_width, second_width) {
        (1, 1) => u64::from(first_index) * WIDTH_1_COUNT + u64::from(second_index),
        (1, 2) => WIDTH_1_PAIRS + u64::from(first_index) * WIDTH_2_COUNT + u64::from(second_index),
        (2, 1) => {
            WIDTH_1_PAIRS
                + WIDTH_1_2_PAIRS
                + u64::from(first_index) * WIDTH_1_COUNT
                + u64::from(second_index)
        }
        _ => return None,
    };
    u16::try_from(value).ok()
}

fn decode_block(chars: &[char]) -> Option<u64> {
    if chars.len() != 8 {
        return None;
    }
    let mut value = 0u64;
    for pair in chars.chunks_exact(2) {
        value = value
            .checked_mul(PAIR_RADIX)?
            .checked_add(u64::from(decode_pair(pair[0], pair[1])?))?;
    }
    (value < (1u64 << BLOCK_BITS)).then_some(value)
}

#[pyfunction]
fn encode_rust(input: Vec<u8>) -> String {
    let mut output = String::new();
    encode_block(input.len() as u64, &mut output);

    let mut reader = BitReader::endian(input.as_slice(), BigEndian);
    let total_bits = input.len() * 8;
    let full_blocks = total_bits / BLOCK_BITS as usize;
    for _ in 0..full_blocks {
        let value = reader.read::<63, u64>().expect("complete input block");
        encode_block(value, &mut output);
    }
    let remaining = total_bits % BLOCK_BITS as usize;
    if remaining != 0 {
        let value = reader
            .read_var::<u64>(remaining as u32)
            .expect("remaining input bits")
            << (BLOCK_BITS as usize - remaining);
        encode_block(value, &mut output);
    }
    output
}

#[pyfunction]
fn decode_rust(input: &str) -> PyResult<Vec<u8>> {
    let chars: Vec<char> = input.chars().collect();
    if chars.len() < 8 || !chars.len().is_multiple_of(8) {
        return Err(PyValueError::new_err(
            "encoded input must contain a size block and complete 8-character blocks",
        ));
    }
    let byte_len =
        decode_block(&chars[..8]).ok_or_else(|| PyValueError::new_err("invalid size block"))?;
    let total_bits = byte_len
        .checked_mul(8)
        .ok_or_else(|| PyValueError::new_err("encoded byte length is too large"))?;
    let expected_blocks =
        total_bits / u64::from(BLOCK_BITS) + u64::from(total_bits % u64::from(BLOCK_BITS) != 0);
    let actual_blocks = ((chars.len() - 8) / 8) as u64;
    if expected_blocks != actual_blocks {
        return Err(PyValueError::new_err(
            "encoded block count does not match the size header",
        ));
    }
    let capacity = usize::try_from(byte_len)
        .map_err(|_| PyValueError::new_err("encoded byte length is too large"))?;
    let final_bits = (total_bits % u64::from(BLOCK_BITS)) as u32;
    let mut output = Vec::with_capacity(capacity);
    {
        let mut writer = BitWriter::endian(&mut output, BigEndian);

        for (index, block) in chars[8..].chunks_exact(8).enumerate() {
            let value =
                decode_block(block).ok_or_else(|| PyValueError::new_err("invalid data block"))?;
            if index + 1 == actual_blocks as usize && final_bits != 0 {
                let padding = BLOCK_BITS - final_bits;
                if value & ((1u64 << padding) - 1) != 0 {
                    return Err(PyValueError::new_err(
                        "non-zero padding in final data block",
                    ));
                }
                writer
                    .write_var(final_bits, value >> padding)
                    .map_err(|err| PyValueError::new_err(err.to_string()))?;
            } else {
                writer
                    .write::<63, u64>(value)
                    .map_err(|err| PyValueError::new_err(err.to_string()))?;
            }
        }
    }
    if output.len() != capacity {
        return Err(PyValueError::new_err(
            "decoded payload length does not match size header",
        ));
    }
    Ok(output)
}

/// A Python module for encoding and decoding using custom base64x32 algorithm
#[pymodule]
fn bookette(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(encode_rust, m)?)?;
    m.add_function(wrap_pyfunction!(decode_rust, m)?)?;
    Ok(())
}
