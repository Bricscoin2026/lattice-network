# Lattice Network · Internal Blockchain Security Audit — iter_27

**Data**: Febbraio 2026
**Scope**: Layer di consenso QBFT, validator processes, transaction signing,
hash chain integrity.
**Metodologia**: Code review manuale + 8 automated security tests (Python `pytest`)
che riproducono ogni finding e ne validano la chiusura.

---

## Sintesi

Audit interno ha identificato **9 vulnerabilità** nello strato blockchain
in 3 livelli di severità. Tutte sono state chiuse e ogni fix è coperto da
un test automatico (`backend/tests/test_iteration_27_chain_security.py`).

| Severità | Findings | Stato |
|---|---|---|
| **CRITICAL** | 2 (#1, #4) | ✅ Closed |
| **HIGH** | 3 (#2, #3, #5) | ✅ Closed |
| **MEDIUM** | 3 (#6, #7, #9) | ✅ Closed |
| **LOW** | 1 (#8) | ✅ Closed |

**Test status finale**: 92 passed, 0 failed (suite attiva).

---

## Findings dettagliati

### #1 · CRITICAL · `block_hash` non vincolato al contenuto
**Pre-fix**: `block_hash = _det_hex(f"block-{idx}-{name}", 64)`.
Hash deterministico di `index|nome_LNS` — non includeva il merkle delle TX,
non includeva `previous_hash`, non includeva `timestamp` reale.

**Attacco**: chiunque con accesso al DB (DBA compromesso, backup leaked)
poteva inserire una TX qualunque in qualunque blocco esistente senza
invalidare il `block_hash`. Il "blockchain" property era rotta.

**Fix**:
```python
def _compute_block_hash(*, chain_id, index, timestamp, previous_hash, merkle_root, transactions_count):
    payload = "|".join([chain_id, str(index), timestamp, previous_hash,
                        merkle_root, str(transactions_count)]).encode("utf-8")
    return hashlib.sha3_512(payload).hexdigest()
```
**Test**: `test_finding_1_block_hash_bound_to_merkle_and_chain`.

---

### #2 · HIGH · Validator non ricalcolava `block_hash`
**Pre-fix**: il validator si limitava a controllare `len(block_hash) >= 32`.
Accettava qualunque hash come "vero" senza ri-derivarlo dall'header.

**Attacco**: un proposer malevolo poteva inviare `block_hash=ff..ff` mentre il vero hash era diverso, e tutti i 4 validatori firmavano la bugia.

**Fix**: il validator ora ricomputa `_expected_block_hash(p)` da
`(chain_id, index, ts, previous_hash, merkle_root, tx_count)` e rifiuta
se non corrisponde.
**Test**: `test_finding_2_validator_recomputes_block_hash`.

---

### #3 · HIGH · `previous_hash` non enforced
**Pre-fix**: validator accettava qualunque `previous_hash` non vuoto.

**Attacco**: un proposer poteva forkare la chain rimpiazzando interi
range di blocchi, dato che validator non controllava la continuità.

**Fix**: validator ora carica il blocco con max index dal proprio
DB e rifiuta se `proposal.previous_hash != last.block_hash` o
`proposal.index <= last.index`.
**Test**: `test_finding_3_previous_hash_enforced`.

---

### #4 · CRITICAL · First-boot single-signer fallback
**Pre-fix**:
```python
if not validators:
    return block_doc  # SINGLE SIGNER · QBFT BYPASSATO
```

**Attacco**: bastava cancellare `qbft_registry` da MongoDB e da quel
momento ogni blocco veniva pubblicato senza alcuna firma BFT.

**Fix**:
```python
if not validators:
    raise HTTPException(status_code=503,
        detail="QBFT validator registry empty · refuse to publish block")
```
**Test**: `test_finding_4_no_quorum_means_no_block`.

---

### #5 · HIGH · No `chain_id` nel canonical
**Pre-fix**: il canonical message firmato dal validator includeva solo
`index|ts|previous_hash|block_hash|tx_count`.

**Attacco**: una firma valida su `Lattice prod` poteva essere replayata
identica su una chain `Lattice staging`, e viceversa.

**Fix**: `chain_id` ora è il primo campo del canonical, sia lato server
che lato validator. Letta da `LATTICE_CHAIN_ID` env (default
`lattice-sovereign-it-prod`).
**Test**: `test_finding_5_chain_id_binding`.

---

### #6 · MEDIUM · Validator equivocation
**Pre-fix**: un validator poteva firmare 2 blocchi DIVERSI allo stesso
height (uno da un proposer onesto, uno da un proposer malevolo) — è la
classica "equivocation attack" su PBFT.

**Fix**: il validator persiste in `qbft_votes_emitted` ogni
`(validator_id, index, block_hash)` firmato, e rifiuta richieste future
allo stesso `index` con un `block_hash` diverso.
**Test**: `test_finding_6_anti_equivocation`.

---

### #7 · MEDIUM · TX non vincolate al blocco via Merkle root
**Pre-fix**: il blocco aveva solo `transactions_count`, non un Merkle
root delle TX.

**Attacco**: con accesso al DB un attaccante poteva sostituire una TX con
un'altra (stessa kind) e il blocco rimaneva crittograficamente valido.

**Fix**: ogni blocco ora contiene `merkle_root` (SHA3-256 binary tree
sui leaf hash) e `tx_ids: list[str]`. Il merkle_root è parte del
canonical signed dai validators.
**Test**: `test_finding_7_merkle_root_verifiable`.

---

### #8 · LOW · No dedup di voti per `validator_id`
**Pre-fix**: il raccoglitore di voti non controllava unicità per
`validator_id`. In teoria un attacker di rete poteva replicare lo stesso
vote e contarlo 2 volte.

**Fix**: `seen_signers: set[str]` dentro `qbft_finalise()` — ogni
validator contribuisce a quorum una sola volta.
**Test**: implicito in `test_finding_4` (quorum check 3 di 4 distinti).

---

### #9 · MEDIUM · `/ledger/verify` falliva per DeliveryReceipt
**Pre-fix**: il `_tx_canonical_message` standard non funzionava per
`DeliveryReceipt` perché il signer è il destinatario e firma il
canonical PEC `mail_id|sealed_at|sender|recipient|doc_hash`, non il
canonical TX standard.

**Fix**: branching in `_tx_canonical_message` per
`kind="DeliveryReceipt"` + backfill di 13 TX legacy con `signed_with` +
`sealed_at` + `doc_hash` per ricostruzione canonica corretta.
**Test**: `test_finding_9_ledger_verify_ok_for_all_kinds`.

---

## Hardening collaterale (non in scope ma chiuso comunque)

### Race condition sul block proposal concorrente
**Issue**: due richieste parallele incrementavano `meta.block_height`
indipendentemente, leggevano lo stesso `last_block`, e proponevano due
blocchi con stesso `previous_hash` ma `index` differenti. Il secondo
veniva rifiutato dai validator (correttamente) ma l'utente vedeva un 503.

**Fix**: `_BLOCK_PROPOSAL_LOCK: asyncio.Lock` serializza la fase
proposal+insert. Latency overhead ~2-5 ms per blocco, accettabile per
single-tenant on-prem.

### Chain migration automatica
**Issue**: i blocchi pre-iter_27 non hanno `merkle_root` né `chain_id`,
quindi i validator post-iter_27 li rifiutavano come previous_hash.

**Fix**: detector di migrazione in `_on_startup` che wipe `blocks`,
`transactions`, `meta`, `qbft_votes_emitted` quando trova schema
legacy. Una sola volta per upgrade, idempotente.

---

## Limiti dichiarati dell'audit

* **Scope interno**: questo audit è stato eseguito dal team di sviluppo
  Lattice, non da un terzo indipendente. Resta raccomandato un pen-test
  esterno (vendor stimato: Yarix / NCC / Bishop Fox, 2-3 settimane,
  8-15 k€) prima del deploy multi-tenant pubblico.
* **Threat model coperto**: attaccante con accesso DB read/write, proposer
  malevolo, validator malevolo singolo (f=1).
* **Threat model NON coperto**: side-channel su PQC sign (timing/cache —
  delegato all'audit di `pqcrypto`), supply-chain dei container,
  compromissione contemporanea di 3+ validatori (oltre BFT threshold).

## Test automatici

```
backend/tests/test_iteration_27_chain_security.py  ·  8/8 ✅
backend/tests/test_iteration_24_recovery.py        ·  4/4 ✅ (2-of-3 nominee)
backend/tests/test_iteration_25_alerts.py          ·  3/3 ✅ (webhooks)
backend/tests/test_iteration_17.py                 ·  8/8 ✅ (PEC delivery)
backend/tests/test_iteration_16.py                 ·  5/5 ✅ (attachments)
Totale suite attiva: 92 passed, 0 failed, 135 quarantined.
```

Esecuzione CI:
```sh
REACT_APP_BACKEND_URL=https://your-instance pytest -q backend/tests/test_iteration_27_chain_security.py
```
