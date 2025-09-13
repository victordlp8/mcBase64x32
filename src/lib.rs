use std::collections::HashMap;
use serde::{Deserialize, Serialize};
use lazy_static::lazy_static;
use bitstream_io::{BitReader, BigEndian, BitRead, BitWriter, BitWrite};
use pyo3::prelude::*;

const BASE_JSON: &str = include_str!("../mcbase64x32/utils/baseList.json");
const BASE64_JSON: &str = include_str!("../mcbase64x32/utils/thinBase64.json");


#[derive(Serialize, Deserialize, Debug)]
struct BaseList {
    encode: Vec<String>,
    decode: HashMap<String, u16>
}

#[derive(Serialize, Deserialize, Debug)]
struct Base64List {
    encode: Vec<String>,
    decode: HashMap<String, u8>
}

lazy_static! {
    static ref MAIN_CONVERSOR: ([String; 2048], HashMap<String, u16>) = {
        let base: BaseList = serde_json::from_str(BASE_JSON).unwrap();

        let arr: [String; 2048] = base.encode
            .try_into()
            .expect("encode must contain exactly 2048 items");

        (arr, base.decode)
    };

    static ref B64_CONVERSOR: ([String; 64], HashMap<String, u8>) = {
        let base: Base64List = serde_json::from_str(BASE64_JSON).unwrap();
        let arr: [String; 64] = base.encode
            .try_into()
            .expect("encode must contain exactly 64 items");
        (arr, base.decode)
    };
}

fn encode_base(input: u16) -> &'static str {
    &MAIN_CONVERSOR.0[input as usize]
}

fn decode_base(input: String) -> u16 {
    MAIN_CONVERSOR.1[&input]
}

fn encode_b64(input: u8) -> &'static str {
    &B64_CONVERSOR.0[input as usize]
}

fn decode_b64(input: String) -> u8 {
    B64_CONVERSOR.1[&input]
}

#[pyfunction]
fn encode_rust(input: Vec<u8>) -> String {
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

    if bits_left == 0{
        return output;
    }
    let extra_bits = reader.read_var::<u16>(bits_left as u32).unwrap();

    if bits_left<=6 {
        let end_data:u8 = (extra_bits as u8) << (6 - bits_left);
        output.push_str(encode_b64(end_data));
    }
    else {
        let end_data =extra_bits<< (11 - bits_left);
        output.push_str(encode_base(end_data));
    }

    output
}

#[pyfunction]
fn decode_rust(input: &str) -> Vec<u8> {
    let mut raw_decoded: Vec<u16> = vec![];
    let inputs_chars: Vec<char> = input.chars().collect();
    for i in (1..inputs_chars.len()).step_by(2) {
        let chunk = inputs_chars[i-1..i+1].iter().collect::<String>();
        let val = decode_base(chunk);
        raw_decoded.push(val);
    }

    let mut output: Vec<u8> = Vec::new();
    let mut writer = BitWriter::endian(&mut output, BigEndian);

    for &numero in &raw_decoded {
        writer.write_var(11, numero).unwrap();
    }

    if inputs_chars.len() % 2 == 1 {
        let last_val = decode_b64(inputs_chars[inputs_chars.len()-1].to_string());
        writer.write_var(6, last_val).unwrap();
    }

    //let padding_bits = ((input.len()/2)*11)%8;

    //println!("{:?}", output);

    output
}

/// A Python module for encoding and decoding using custom base64x32 algorithm
#[pymodule]
fn mcbase64x32(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(encode_rust, m)?)?;
    m.add_function(wrap_pyfunction!(decode_rust, m)?)?;
    Ok(())
}