# `lattice-crypto` — WebAssembly Build

`lattice-crypto` ships with a `cdylib` crate type and a `wasm`
feature flag so it can be cross-compiled to **WebAssembly** and
loaded directly inside a browser, an Electron client, or a Node
relay (cfr. SCORPION spec — *"compilatori dei core crittografici
in WebAssembly (WASM)"*).

## Toolchain

```bash
rustup target add wasm32-unknown-unknown
cargo install wasm-pack
```

## Build

```bash
# Build the JS/WASM bundle for a browser ESM consumer.
wasm-pack build core/lattice-crypto \
    --release \
    --target web \
    --features wasm \
    --out-dir ../../dist/lattice-crypto-wasm

# Build a Node.js consumer (used by the relay nodes).
wasm-pack build core/lattice-crypto \
    --release \
    --target nodejs \
    --features wasm \
    --out-dir ../../dist/lattice-crypto-wasm-node
```

The resulting bundle exposes:

* `compute_sha3_512(payload)`
* `compute_sha3_256(payload)`
* `verify_pqc_signature(data, signature, public_key)` (ML-DSA-65 / FIPS 204)
* `kem_encapsulate(peer_pk)` / `kem_decapsulate(ct, sk)` (ML-KEM-768 / FIPS 203)
* `fingerprint_pubkey(public_key)` — SAS-style 8-byte fingerprint

## Browser consumption (TypeScript)

```ts
import init, { compute_sha3_512, fingerprint_pubkey } from "lattice-crypto-wasm";
await init();
const hash = compute_sha3_512(new TextEncoder().encode("hello sovereign"));
console.log(fingerprint_pubkey(somePublicKey));
```

## Reproducible build

`lattice-crypto` declares `getrandom = { features = ["js"] }` under
`cfg(target_arch = "wasm32")` so the wasm bundle pulls entropy from
`crypto.getRandomValues()` in the browser and `crypto.randomBytes()`
in Node — the same path used by the rest of the Web Crypto API.

> **Note** — the closed-source `prod/zk-rln-prover` crate (Groth16
> over BN254) is *not* part of the WASM bundle. Browsers only need
> the verifier path which lives in the open-core `lattice-zk-rln`.
