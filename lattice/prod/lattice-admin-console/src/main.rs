//! Lattice Network — Sovereign Admin Console (Console Dorata).
//!
//! Proprietary closed-source backend that exposes ledger control
//! operations (LNS revocation, identity registration, audit
//! queries) to the React/TypeScript "Sovereign Gold & Dark Slate"
//! administration UI.

use lattice_node::{SovereignChain, Transaction, TransactionPayload};

/// Per-extrinsic weight (frame_support style).
pub const WEIGHT_IDENTITY_REVOKE: u64 = 10_000;
pub const WEIGHT_IDENTITY_REGISTER: u64 = 14_000;

/// Top-level controller used by the admin console HTTP layer.
pub struct AdminController {
    pub ledger: SovereignChain,
    /// Local admin nonce — incremented on each successful submit.
    pub admin_nonce: u64,
}

impl AdminController {
    /// Forcefully revoke a Lattice Name Service identity. The
    /// revocation is itself a PQC-signed sovereign extrinsic
    /// and is finalised in its own block for legal auditability.
    pub fn force_revoke_user_lns(&mut self, name: String, admin_kp: &lattice_crypto::LatticeKeyPair) {
        let payload = TransactionPayload::IdentityRevoke { lns_name: name };
        let serialized = serde_json::to_vec(&payload)
            .expect("IdentityRevoke payload must serialise");
        let signature = admin_kp.sign_data(&serialized);

        let tx = Transaction {
            payload,
            sender_public_key: admin_kp.public_key.clone(),
            signature,
            nonce: self.admin_nonce,
            weight: WEIGHT_IDENTITY_REVOKE,
        };
        if self.ledger.submit_transaction(tx).is_ok() {
            self.admin_nonce = self.admin_nonce.wrapping_add(1);
        }
        self.ledger.process_block();
    }

    /// Register a new sovereign identity on-chain.
    pub fn register_user_lns(
        &mut self,
        lns_name: String,
        did: String,
        identity_pk: Vec<u8>,
        admin_kp: &lattice_crypto::LatticeKeyPair,
    ) {
        let payload = TransactionPayload::IdentityRegister {
            lns_name,
            did,
            public_key: identity_pk,
        };
        let serialized = serde_json::to_vec(&payload)
            .expect("IdentityRegister payload must serialise");
        let signature = admin_kp.sign_data(&serialized);

        let tx = Transaction {
            payload,
            sender_public_key: admin_kp.public_key.clone(),
            signature,
            nonce: self.admin_nonce,
            weight: WEIGHT_IDENTITY_REGISTER,
        };
        if self.ledger.submit_transaction(tx).is_ok() {
            self.admin_nonce = self.admin_nonce.wrapping_add(1);
        }
        self.ledger.process_block();
    }
}

fn main() {
    let ledger = SovereignChain::new();
    let admin_kp = lattice_crypto::LatticeKeyPair::generate_pqc_identity();
    let mut controller = AdminController { ledger, admin_nonce: 0 };
    controller.force_revoke_user_lns(
        "ex-dipendente.azienda.id".to_string(),
        &admin_kp,
    );
    println!("Lattice Admin Console Core Online. Revocation TX executed on local State.");
}
