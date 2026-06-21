//! Lattice Network — Certify SMTP → Sovereign-Notary Gateway.
//!
//! Proprietary closed-source module. Wraps the legacy SMTP outbound
//! flow and emits a notarised on-chain audit trail (NotaryTX) for
//! every outbound corporate message. Each emitted extrinsic carries
//! a sender nonce and a pre-computed weight, in line with the
//! Substrate-style `lattice-node` runtime.

use lattice_crypto::compute_sha3_512;
use lattice_node::{Transaction, TransactionPayload};

/// Per-message weight contributed by a NotarySeal extrinsic.
pub const WEIGHT_NOTARY_SEAL: u64 = 12_500;

/// The gateway holds the sovereign identity used to sign every
/// emitted NotaryTX. In production this key lives inside an HSM.
pub struct CertifyMailGateway {
    pub identity_key: lattice_crypto::LatticeKeyPair,
    /// Local view of the gateway's sender nonce. Bumped on every
    /// emitted NotaryTX.
    pub local_nonce: u64,
}

impl CertifyMailGateway {
    /// Hash the raw RFC-5322 message, build a sovereign
    /// `NotarySeal` payload, and PQC-sign the canonical
    /// serialisation. The returned `Transaction` is ready to be
    /// submitted to the local `SovereignChain` mempool.
    pub fn process_legacy_smtp_outbound(&mut self, raw_email: &[u8], metadata: String) -> Transaction {
        let email_hash = compute_sha3_512(raw_email);
        let payload = TransactionPayload::NotarySeal {
            doc_hash: email_hash,
            metadata,
        };
        let serialized = serde_json::to_vec(&payload)
            .expect("NotarySeal payload must serialise");
        let signature = self.identity_key.sign_data(&serialized);

        let tx = Transaction {
            payload,
            sender_public_key: self.identity_key.public_key.clone(),
            signature,
            nonce: self.local_nonce,
            weight: WEIGHT_NOTARY_SEAL,
        };
        self.local_nonce = self.local_nonce.wrapping_add(1);
        tx
    }
}

fn main() {
    let kp = lattice_crypto::LatticeKeyPair::generate_pqc_identity();
    let mut gateway = CertifyMailGateway { identity_key: kp, local_nonce: 0 };
    let sample_mail = b"From: ceo@azienda.id\nTo: cfo@azienda.id\nSubject: Secret\n\nContent";
    let tx = gateway.process_legacy_smtp_outbound(
        sample_mail,
        "Corporate Outbound Audit Trail".to_string(),
    );
    println!(
        "Certify Mail Gateway online. NotaryTX generated successfully. Sig prefix: {:?}",
        tx.signature[0..10].to_vec()
    );
}
