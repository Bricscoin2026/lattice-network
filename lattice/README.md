# Lattice Network — Cargo Workspace

Sovereign tokenless blockchain ecosystem for on-premise enterprise
deployment. Pure-Rust, post-quantum-secure, QBFT-finalised.

## Workspace layout

```
lattice/
├── Cargo.toml                              # Workspace root
├── core/                                   # Open Core — BSL 1.1
│   ├── lattice-crypto/                     # Dilithium3 + SHA3-512 + AES-GCM
│   ├── lattice-node/                       # Sovereign tokenless ledger
│   └── pulse-protocol/                     # Sealed-sender onion chat
└── prod/                                   # Closed Source — Commercial
    ├── certify-gateway/                    # SMTP → Notary gateway
    └── lattice-admin-console/              # Console Dorata backend
```

## Build

```bash
cd lattice
cargo build --workspace --release
```

## Run smoke targets

```bash
cargo run -p certify-gateway
cargo run -p lattice-admin-console
```

## Licensing

| Module                     | License                           |
| -------------------------- | --------------------------------- |
| `core/lattice-crypto`      | Business Source License 1.1       |
| `core/lattice-node`        | Business Source License 1.1       |
| `core/pulse-protocol`      | Business Source License 1.1       |
| `prod/certify-gateway`     | Lattice Commercial (proprietary)  |
| `prod/lattice-admin-console` | Lattice Commercial (proprietary)|
