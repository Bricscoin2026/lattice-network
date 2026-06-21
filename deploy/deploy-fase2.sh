#!/usr/bin/env bash
# ============================================================================
# Lattice Network — FASE 2 + FASE 3 (M1/M2/M3) deploy script
# ============================================================================
# Esegui SUL SERVER HETZNER (167.233.85.189) DOPO il git pull.
#
# Uso:
#   ssh root@167.233.85.189
#   cd /opt/lattice
#   bash deploy/deploy-fase2.sh
#
# Cosa fa:
#   1. git pull dell'ultimo commit
#   2. Ricompila l'immagine backend, che ora produce 3 binari Rust:
#        - qbft-validator   (FASE 2)
#        - mixnet-relay     (FASE 2)
#        - lattice-gateway  (FASE 3 — 12 read endpoints + POST /leads)
#   3. Pulisce le vecchie keypair Dilithium3 nel keystore (i binari Rust
#      si auto-rigenerano come ML-DSA-65 FIPS 204 al primo boot)
#   4. Restart container backend
#   5. Verifica salute
#
# Tempo: ~8-10 min (compilazione Rust 5-7 min + restart 1 min)
# ============================================================================

set -euo pipefail

GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
log() { echo -e "${GREEN}[deploy]${NC} $*"; }
warn() { echo -e "${YELLOW}[warn]${NC} $*"; }
die() { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

cd "$(dirname "$0")/.."

[[ -f deploy/docker-compose.yml ]] || die "lancia lo script dalla root del repo (cd /opt/lattice)"

log "1/5 · Pull dell'ultima versione da GitHub"
git fetch origin
git pull --ff-only origin main || die "git pull fallito — risolvi conflitti manualmente"

log "2/5 · Rebuild dell'immagine backend (compila i binari Rust nativi)"
log "      Stack 1: PyO3 wheel · Stack 2: qbft-validator + mixnet-relay"
log "      Prima compilazione ~5 min sui 2 vCPU del Hetzner, poi cached."
docker compose -f deploy/docker-compose.yml build backend

log "3/5 · Migrazione keystore — cancello le vecchie keypair Dilithium3"
log "      (i nuovi binari Rust le rigenereranno come ML-DSA-65 FIPS 204)"
source deploy/.env.production 2>/dev/null || warn "no .env.production found, skipping mongo cleanup (binaries will self-migrate at boot)"
if [[ -n "${MONGO_INITDB_ROOT_USERNAME:-}" ]]; then
  docker compose -f deploy/docker-compose.yml exec -T mongo \
    mongosh -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin \
    --eval "
      db = db.getSiblingDB('${DB_NAME:-lattice}');
      var r1 = db.keystore.deleteMany({entity: {\$in: ['VAL-01','VAL-02','VAL-03','VAL-04']}});
      var r2 = db.mixnet_keystore.deleteMany({});
      var r3 = db.qbft_registry.deleteMany({});
      var r4 = db.qbft_votes_emitted.deleteMany({});
      print('cleared: keystore=' + r1.deletedCount + ', mixnet_keystore=' + r2.deletedCount + ', qbft_registry=' + r3.deletedCount + ', qbft_votes_emitted=' + r4.deletedCount);
    " || warn "mongo cleanup failed — il binario Rust farà self-migration al boot"
fi

log "4/5 · Restart dei container con la nuova immagine"
docker compose -f deploy/docker-compose.yml up -d backend
sleep 8

log "5/5 · Verifica salute dei processi Rust"
docker compose -f deploy/docker-compose.yml exec -T backend supervisorctl status

echo ""
log "==== STATO BLOCKCHAIN ===="
curl -s https://lattice-network.it/api/qbft/status | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'  Validators online: {d[\"live_count\"]}/{d[\"total_count\"]} (quorum reached: {d[\"quorum_reached\"]})')
for v in d['validators']:
    print(f'    - {v[\"validator_id\"]} fp={v[\"pk_fingerprint\"][:16]}... signed={v[\"signed_total\"]}')
"
curl -s https://lattice-network.it/api/mixnet/status | python3 -c "
import sys,json
d=json.load(sys.stdin)
print(f'  Mixnet relays online: {d[\"live_count\"]}/{d[\"total_count\"]}')
"
echo ""
log "DEPLOY FASE 2 COMPLETATO. Blockchain ora gira su binari Rust nativi."
log "Visita https://lattice-network.it/qbft per la console live."
