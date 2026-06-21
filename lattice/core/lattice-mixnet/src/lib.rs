//! Lattice Network — Loopix-style sealed-sender mixnet.
//!
//! Three-hop onion-routed relay network with Poisson cover-traffic
//! padding. The outer onion layers use ML-KEM-768 KEM-derived AEAD
//! keys, the inner sealed-sender envelope is the
//! `SealedSenderPacket` produced by `pulse-protocol`.

use lattice_crypto::{compute_sha3_256, compute_sha3_512};
use serde::{Serialize, Deserialize};

/// One relay in the Lattice mixnet topology.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct MixnetRelay {
    pub node_id: String,
    pub label: String,
    pub region: String,
    pub kem_pk: Vec<u8>,
    pub latency_ms: u32,
    pub layer: u8,
}

/// One hop of a built route (output of `build_route`).
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct MixnetHop {
    pub layer: u8,
    pub relay_node_id: String,
    pub relay_label: String,
    pub relay_region: String,
    pub onion_layer_hash: [u8; 32],
    pub delay_ms: u32,
}

/// A complete encrypted route from origin to destination LNS.
#[derive(Debug, Serialize, Deserialize, Clone)]
pub struct MixnetRoute {
    pub route_id: String,
    pub origin_lns: String,
    pub destination_lns: String,
    pub hops: Vec<MixnetHop>,
    pub total_delay_ms: u32,
    pub cover_traffic_rate_hz: f32,
}

/// Select 3 relays (one per layer) and build a deterministic route
/// id from the per-hop onion-layer hashes.
pub fn build_route(
    relays: &[MixnetRelay],
    origin_lns: &str,
    destination_lns: &str,
    seed: u64,
) -> Result<MixnetRoute, &'static str> {
    if relays.len() < 3 {
        return Err("Mixnet: at least 3 relays required");
    }
    let mut layers: [Vec<&MixnetRelay>; 3] = [Vec::new(), Vec::new(), Vec::new()];
    for r in relays {
        if (r.layer as usize) < 3 {
            layers[r.layer as usize].push(r);
        }
    }
    for l in 0..3 {
        if layers[l].is_empty() {
            return Err("Mixnet: empty topology layer");
        }
    }
    let mut hops: Vec<MixnetHop> = Vec::with_capacity(3);
    let mut total = 0u32;
    let mut acc = compute_sha3_512(&seed.to_be_bytes());
    for layer in 0..3u8 {
        let bucket = &layers[layer as usize];
        let pick_idx = (u64::from_be_bytes(acc[..8].try_into().unwrap()) as usize) % bucket.len();
        let relay = bucket[pick_idx];
        acc = compute_sha3_512(&acc);
        let mut buf = Vec::new();
        buf.extend_from_slice(b"LATTICE-LOOPIX-v1|");
        buf.extend_from_slice(origin_lns.as_bytes());
        buf.extend_from_slice(b"|");
        buf.extend_from_slice(destination_lns.as_bytes());
        buf.extend_from_slice(b"|layer=");
        buf.push(layer);
        buf.extend_from_slice(relay.node_id.as_bytes());
        let onion_layer_hash = compute_sha3_256(&buf);
        let delay = relay.latency_ms.saturating_add(15 * (layer as u32 + 1));
        total = total.saturating_add(delay);
        hops.push(MixnetHop {
            layer,
            relay_node_id: relay.node_id.clone(),
            relay_label: relay.label.clone(),
            relay_region: relay.region.clone(),
            onion_layer_hash,
            delay_ms: delay,
        });
    }
    let mut id_input = Vec::new();
    for h in &hops {
        id_input.extend_from_slice(&h.onion_layer_hash);
    }
    let route_id_full = compute_sha3_256(&id_input);
    let route_id = route_id_full
        .iter()
        .take(12)
        .map(|b| format!("{:02x}", b))
        .collect::<String>();

    Ok(MixnetRoute {
        route_id: format!("route-{}", route_id),
        origin_lns: origin_lns.to_string(),
        destination_lns: destination_lns.to_string(),
        hops,
        total_delay_ms: total,
        cover_traffic_rate_hz: 1.5,
    })
}
