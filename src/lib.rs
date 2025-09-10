use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use lazy_static::lazy_static;
use bitstream_io::{BitReader, BigEndian, BitRead, BitWriter, BitWrite};
use pyo3::prelude::*;

const GAME_JSON: &str = include_str!("../mcbase64x32/utils/baseList.json");

#[derive(Serialize, Deserialize, Debug)]
struct BaseList {
    encode: Vec<String>,
    decode: HashMap<String, u16>
}

lazy_static! {
    static ref CONVERSOR: ([String; 2048], HashMap<String, u16>) = {
        let base: BaseList = serde_json::from_str(GAME_JSON).unwrap();

        // Convert Vec<String> into [String; 2048]
        let arr: [String; 2048] = base.encode
            .try_into()
            .expect("encode must contain exactly 2048 items");

        (arr, base.decode)
    };
}

fn encode_base(input: u16) -> &'static str {
    &CONVERSOR.0[input as usize]
}

fn decode_base(input: String) -> u16 {
    CONVERSOR.1[&input]
}

#[pyfunction]
fn encode(input: Vec<u8>) -> String {
    let mut output = String::new();

    let mut reader = BitReader::endian(&input[..], BigEndian);
    let total_bits = input.len() * 8;
    let complete_chunks = total_bits / 11;

    // Read complete 11-bit chunks
    for _ in 0..complete_chunks {
        let val = reader.read::<11, u16>().unwrap();
        output.push_str(encode_base(val));
    }

    // Handle remaining bits if any
    let bits_left = total_bits % 11;
    if bits_left != 0 {
        let extra = reader.read_var::<u16>(bits_left as u32)
            .unwrap() << (11 - bits_left);
        output.push_str(encode_base(extra));
    }

    output
}

#[pyfunction]
fn decode(input: &str) -> Vec<u8> {
    let mut raw_decoded: Vec<u16> = vec![];
    let inputs_chars: Vec<char> = input.chars().collect();
    for i in (0..inputs_chars.len()).step_by(2) {
        let chunk = inputs_chars[i..i+2].iter().collect::<String>();
        let val = decode_base(chunk);
        raw_decoded.push(val);
    }

    let mut output: Vec<u8> = Vec::new();
    let mut writer = BitWriter::endian(&mut output, BigEndian);

    for &numero in &raw_decoded {
        writer.write_var(11, numero).unwrap();
    }

    let padding_bits = ((input.len()/2)*11)%8;

    if padding_bits >= 8 {
        output.pop();
    }

    output
}

/// A Python module for encoding and decoding using custom base64x32 algorithm
#[pymodule]
fn mcbase64x32(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(encode, m)?)?;
    m.add_function(wrap_pyfunction!(decode, m)?)?;
    Ok(())
}