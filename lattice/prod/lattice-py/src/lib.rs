//! Lattice Network — Python FFI bindings (PyO3)
//!
//! Esponi i primitivi crittografici del crate Rust open-core
//! `lattice-crypto` al backend FastAPI Python. Tutta la crittografia
//! è eseguita realmente in Rust nativo (no fallback Python).
//!
//! Funzioni esposte:
//! * `sha3_512_hex(payload: bytes) -> str`
//! * `sha3_256_hex(payload: bytes) -> str`
//! * `fingerprint_pubkey(pk: bytes) -> str`
//! * `ml_dsa_65_keypair() -> (bytes, bytes)`  (pk, sk)
//! * `ml_dsa_65_sign(sk: bytes, msg: bytes) -> bytes`
//! * `ml_dsa_65_verify(pk: bytes, msg: bytes, sig: bytes) -> bool`
//! * `version() -> str`

use pyo3::prelude::*;
use pyo3::types::PyBytes;
use lattice_crypto as lc;

#[pyfunction]
fn sha3_512_hex(payload: &[u8]) -> String {
    hex::encode(lc::compute_sha3_512(payload))
}

#[pyfunction]
fn sha3_256_hex(payload: &[u8]) -> String {
    hex::encode(lc::compute_sha3_256(payload))
}

#[pyfunction]
fn fingerprint_pubkey(pk: &[u8]) -> String {
    lc::fingerprint_pubkey(pk)
}

#[pyfunction]
fn ml_dsa_65_keypair(py: Python<'_>) -> (PyObject, PyObject) {
    let kp = lc::LatticeKeyPair::generate_pqc_identity();
    (
        PyBytes::new_bound(py, &kp.public_key).into(),
        PyBytes::new_bound(py, &kp.secret_key).into(),
    )
}

#[pyfunction]
fn ml_dsa_65_sign(py: Python<'_>, sk: &[u8], msg: &[u8]) -> PyObject {
    let kp = lc::LatticeKeyPair {
        public_key: Vec::new(),
        secret_key: sk.to_vec(),
    };
    let sig = kp.sign_data(msg);
    PyBytes::new_bound(py, &sig).into()
}

#[pyfunction]
fn ml_dsa_65_verify(pk: &[u8], msg: &[u8], sig: &[u8]) -> bool {
    lc::verify_pqc_signature(msg, sig, pk)
}

#[pyfunction]
fn version() -> &'static str {
    concat!(
        "lattice-py v",
        env!("CARGO_PKG_VERSION"),
        " · lattice-crypto FFI · PyO3 · NIST FIPS 202/204"
    )
}

#[pymodule]
fn lattice_py(_py: Python<'_>, m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(sha3_512_hex, m)?)?;
    m.add_function(wrap_pyfunction!(sha3_256_hex, m)?)?;
    m.add_function(wrap_pyfunction!(fingerprint_pubkey, m)?)?;
    m.add_function(wrap_pyfunction!(ml_dsa_65_keypair, m)?)?;
    m.add_function(wrap_pyfunction!(ml_dsa_65_sign, m)?)?;
    m.add_function(wrap_pyfunction!(ml_dsa_65_verify, m)?)?;
    m.add_function(wrap_pyfunction!(version, m)?)?;
    Ok(())
}
