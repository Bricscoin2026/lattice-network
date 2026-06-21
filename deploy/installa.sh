#!/usr/bin/env bash
# =============================================================================
# Lattice Network — Installer guidato self-hosted
# =============================================================================
# Da eseguire sul VPS del cliente, una sola volta:
#   cd /opt/lattice && bash deploy/installa.sh
#
# Lo script:
#   1. Verifica i prerequisiti (Docker, Docker Compose, OpenSSL)
#   2. Chiede via prompt i 4 dati necessari (dominio, email, etc.)
#   3. Genera tutti i secret crittografici sicuri (JWT, envelope, backup)
#   4. Scrive .env.production con permessi 600
#   5. Builda e avvia i container (~10-15 min)
#   6. Esegue il bootstrap del Platform Operator
#   7. Stampa keypair + recovery code da salvare offline
# =============================================================================

set -euo pipefail

# Colori per il terminale
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$SCRIPT_DIR/.env.production"
COMPOSE="docker compose -f $SCRIPT_DIR/docker-compose.yml"

banner() {
  echo -e "\n${BLUE}${BOLD}════════════════════════════════════════════════════════════════════${NC}"
  echo -e "${BLUE}${BOLD}  $1${NC}"
  echo -e "${BLUE}${BOLD}════════════════════════════════════════════════════════════════════${NC}\n"
}

ask() {
  local prompt="$1" default="${2:-}" value
  if [ -n "$default" ]; then
    read -r -p "$(echo -e "${BOLD}$prompt${NC} [${YELLOW}$default${NC}]: ")" value
    echo "${value:-$default}"
  else
    read -r -p "$(echo -e "${BOLD}$prompt${NC}: ")" value
    echo "$value"
  fi
}

confirm() {
  read -r -p "$(echo -e "${YELLOW}$1 [y/N]:${NC} ")" -n 1 ans; echo
  [[ "$ans" =~ ^[Yy]$ ]]
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo -e "${RED}✗ Comando richiesto non trovato: $1${NC}"
    echo "  Installa con: $2"
    exit 1
  }
  echo -e "${GREEN}✓${NC} $1 trovato"
}

# -----------------------------------------------------------------------------
# Step 0 — Prerequisiti
# -----------------------------------------------------------------------------
banner "Lattice Network · Installer guidato"

echo "Verifico i prerequisiti del sistema…"
require_cmd docker "curl -fsSL https://get.docker.com | sh"
require_cmd openssl "apt install -y openssl"
docker compose version >/dev/null 2>&1 || {
  echo -e "${RED}✗ Docker Compose v2 non disponibile${NC}"
  echo "  Installa con: apt install -y docker-compose-plugin"
  exit 1
}
echo -e "${GREEN}✓${NC} docker compose v2"

if [ ! -f "$SCRIPT_DIR/docker-compose.yml" ]; then
  echo -e "${RED}✗ docker-compose.yml non trovato in $SCRIPT_DIR${NC}"
  echo "  Esegui lo script DA DENTRO il repository clonato:"
  echo "    cd /opt/lattice && bash deploy/installa.sh"
  exit 1
fi

# -----------------------------------------------------------------------------
# Step 1 — Esiste già un'installazione?
# -----------------------------------------------------------------------------
if [ -f "$ENV_FILE" ]; then
  echo -e "\n${YELLOW}⚠ Esiste già un .env.production.${NC}"
  if ! confirm "Vuoi sovrascriverlo? (i secret esistenti saranno persi)"; then
    echo "Installazione annullata. Per riavviare lo stack: cd $SCRIPT_DIR && $COMPOSE up -d"
    exit 0
  fi
  cp "$ENV_FILE" "${ENV_FILE}.bak.$(date +%s)"
  echo -e "${GREEN}✓${NC} backup salvato in ${ENV_FILE}.bak.*"
fi

# -----------------------------------------------------------------------------
# Step 2 — Input utente (4 prompt totali)
# -----------------------------------------------------------------------------
banner "Configurazione · 4 domande"

DOMAIN_APP=$(ask "Dominio frontend pubblico" "app.lattice.tuaazienda.it")
DOMAIN_API=$(ask "Dominio API backend" "api.lattice.tuaazienda.it")
ADMIN_LNS=$(ask "LNS Platform Operator (tuo nome.sovereign.lattice.id)" "admin.sovereign.lattice.id")
ADMIN_NAME=$(ask "Nome completo Platform Operator" "Mario Rossi")

# -----------------------------------------------------------------------------
# Step 3 — Genera tutti i secret crittografici
# -----------------------------------------------------------------------------
banner "Generazione secret crittografici"

MONGO_PASS=$(openssl rand -base64 40 | tr -d '/+=' | cut -c1-40)
JWT_SECRET=$(openssl rand -hex 32)
ENVELOPE_KEY=$(openssl rand -hex 32)
BACKUP_PASS=$(openssl rand -base64 48 | tr -d '/+=' | cut -c1-48)

echo -e "${GREEN}✓${NC} MONGO_ROOT_PASSWORD generata (40 char)"
echo -e "${GREEN}✓${NC} LATTICE_JWT_SECRET generata (64 hex)"
echo -e "${GREEN}✓${NC} LATTICE_ENVELOPE_KEY generata (64 hex, AES-256)"
echo -e "${GREEN}✓${NC} BACKUP_PASSPHRASE generata (48 char)"

# -----------------------------------------------------------------------------
# Step 4 — Scrivi .env.production
# -----------------------------------------------------------------------------
banner "Scrittura .env.production"

cat > "$ENV_FILE" <<EOF
# Lattice .env.production — generato da installa.sh il $(date -u +%Y-%m-%dT%H:%M:%SZ)
# NON committare mai questo file. Permessi forzati a 600.

# MongoDB
MONGO_ROOT_USER=lattice_root
MONGO_ROOT_PASSWORD=$MONGO_PASS
DB_NAME=lattice_prod

# Backend
LATTICE_JWT_SECRET=$JWT_SECRET
LATTICE_STRICT_AUTH=1
LATTICE_ENVELOPE_KEY=$ENVELOPE_KEY
CORS_ORIGINS=https://$DOMAIN_APP

# Frontend build
REACT_APP_BACKEND_URL=https://$DOMAIN_API

# Cloudflare Tunnel (compila DOPO aver creato il tunnel su one.dash.cloudflare.com)
CLOUDFLARE_TUNNEL_TOKEN=

# Backup encryption
BACKUP_PASSPHRASE=$BACKUP_PASS
EOF
chmod 600 "$ENV_FILE"
echo -e "${GREEN}✓${NC} $ENV_FILE scritto (mode 600)"

# -----------------------------------------------------------------------------
# Step 5 — Build & start
# -----------------------------------------------------------------------------
banner "Build container · ~10-15 minuti (Rust + WASM + React)"

if confirm "Procedo con docker compose build & up adesso?"; then
  cd "$SCRIPT_DIR"
  $COMPOSE build
  $COMPOSE up -d mongo
  echo "Attendo che Mongo sia healthy…"
  for _ in $(seq 1 30); do
    if $COMPOSE ps mongo | grep -q "healthy"; then break; fi
    sleep 2
  done
  $COMPOSE up -d backend
  echo "Attendo che il backend risponda…"
  for _ in $(seq 1 30); do
    if docker exec "$($COMPOSE ps -q backend)" curl -fsS http://127.0.0.1:8001/api/health >/dev/null 2>&1; then break; fi
    sleep 2
  done
  $COMPOSE --profile full up -d frontend 2>/dev/null || true
  $COMPOSE up -d mongo-backup
  echo -e "${GREEN}✓${NC} stack avviato"
else
  echo "Skipping container start. Esegui manualmente con:  cd $SCRIPT_DIR && $COMPOSE up -d --build"
  exit 0
fi

# -----------------------------------------------------------------------------
# Step 6 — Bootstrap Platform Operator
# -----------------------------------------------------------------------------
banner "Creazione account Platform Operator"

mkdir -p "$SCRIPT_DIR/secrets"
KEYPAIR_HOST_PATH="$SCRIPT_DIR/secrets/${ADMIN_LNS}.keypair.json"

$COMPOSE exec -T backend python -m scripts.bootstrap_sovereign \
  --lns "$ADMIN_LNS" \
  --display-name "$ADMIN_NAME" \
  --output "/secrets/${ADMIN_LNS}.keypair.json"

# Copia il file fuori dal container per renderlo facile da scaricare via scp
docker cp "$($COMPOSE ps -q backend):/secrets/${ADMIN_LNS}.keypair.json" "$KEYPAIR_HOST_PATH" 2>/dev/null || true
chmod 600 "$KEYPAIR_HOST_PATH" 2>/dev/null || true

# -----------------------------------------------------------------------------
# Step 7 — Riepilogo finale
# -----------------------------------------------------------------------------
banner "Installazione completata"

cat <<EOF
${GREEN}${BOLD}✓ Lattice Network installato correttamente.${NC}

${BOLD}Prossimi passi MANUALI:${NC}

  1. ${YELLOW}Scarica il .keypair.json offline${NC} (è l'unica copia della tua chiave segreta):
       scp root@${HOSTNAME:-TUO_VPS}:$KEYPAIR_HOST_PATH ~/lattice/

  2. ${YELLOW}Annota il RECOVERY CODE${NC} stampato sopra in DUE posti offline
     (carta + password manager). Senza, non potrai recuperare l'account.

  3. ${YELLOW}Cancella il .keypair.json dal server${NC} dopo averlo scaricato:
       rm $KEYPAIR_HOST_PATH

  4. ${YELLOW}Configura Cloudflare Tunnel${NC}:
       - Vai su https://one.dash.cloudflare.com → Networks → Tunnels → Create
       - Service interno:    http://backend:8001
       - Public hostname:    $DOMAIN_API
       - Copia il token che ti dà Cloudflare
       - Editalo in $ENV_FILE alla riga CLOUDFLARE_TUNNEL_TOKEN
       - Riavvia:           cd $SCRIPT_DIR && $COMPOSE --profile tunnel up -d cloudflared

  5. ${YELLOW}Deploy del frontend${NC} (Cloudflare Pages oppure container locale):
       - Cloudflare Pages:   connetti il repo GitHub, build command
                             "cd frontend && yarn install --frozen-lockfile && yarn build"
                             output dir: frontend/build
                             env var:    REACT_APP_BACKEND_URL=https://$DOMAIN_API

  6. ${YELLOW}Login${NC} con il .keypair.json scaricato:
       https://$DOMAIN_APP/login

${BOLD}Operazioni quotidiane:${NC}
  - Stato:        cd $SCRIPT_DIR && $COMPOSE ps
  - Logs live:    cd $SCRIPT_DIR && $COMPOSE logs -f backend
  - Backup:       automatici ogni notte alle 03:00 in $SCRIPT_DIR/backups/
  - Aggiorna:     cd $REPO_DIR && git pull && cd deploy && $COMPOSE up -d --build

${RED}${BOLD}IMPORTANTE PER SICUREZZA:${NC}
  - Salva $ENV_FILE OFFLINE (contiene la master key di tutti i tuoi dati).
  - Configura il firewall UFW per esporre SOLO la porta 22 (SSH):
       ufw default deny incoming && ufw allow ssh && ufw enable

EOF
