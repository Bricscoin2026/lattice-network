# Lattice Network · Quick Start Guide

## Installazione one-click (Ubuntu 22.04+ / Debian 12+)

```bash
# 1. Scarica il pacchetto sulla VM
git clone https://your-private-repo/lattice-deploy.git /opt/lattice
cd /opt/lattice

# 2. Lancia l'installer (Compliance mode di default)
sudo ./install.sh --domain mycompany.example.com --mode compliance

# 3. Per ambienti whistleblowing (mixnet attivo)
sudo ./install.sh --domain mycompany.example.com --mode whistleblowing
```

L'installer:
1. ✅ Verifica Docker / openssl / curl (li installa se mancanti)
2. ✅ Genera 5 segreti crittografici random in `.env` (chmod 600)
3. ✅ Crea certificato TLS self-signed (sostituibile con Let's Encrypt)
4. ✅ Avvia stack docker-compose (Mongo + Backend + 4 QBFT + 3 Mixnet + Frontend)
5. ✅ Configura backup automatici orari in `/opt/lattice/backups/`
6. ✅ Stampa URL admin + passphrase iniziale

## SysAdmin CLI: `lattice-admin`

Da terminale (anche via SSH, senza UI):

```bash
# Configurazione automatica (legge frontend/.env), oppure:
export LATTICE_ADMIN_URL=https://my-lattice.azienda.it

# One-pane status
./lattice-admin health

# Licenze
./lattice-admin license status
./lattice-admin license install ./customer.lic
./lattice-admin license reload

# Keystore (chiave master at-rest)
./lattice-admin secrets status
./lattice-admin secrets unlock                    # chiede passphrase
./lattice-admin secrets init                      # primo setup, passphrase ≥12 char

# Backup completo del DB applicativo
./lattice-admin backup snapshot --out backup-$(date +%F).json
./lattice-admin backup restore ./backup-2026-01-01.json --yes

# OpenTimestamps (Bitcoin anchor)
./lattice-admin ots status
./lattice-admin ots anchor                        # nuovo anchor del ledger
./lattice-admin ots upgrade-all                   # promuove anchors pendenti
./lattice-admin ots download <anchor_id> -o proof.ots
```

Lo script ha zero dipendenze esterne (solo Python 3.11+ standard library)
e ritorna exit code != 0 in caso di errori — utile in cron jobs.


## Modalità operative

| Modalità | Mixnet | Tracciabilità | Target |
|---|---|---|---|
| `compliance` (default) | OFF | Completa, log forensi | Banche, PA, studi legali, assicurazioni |
| `whistleblowing` | ON (3-hop) | Anonima, no metadata | Giornalismo, attivismo, segnalazioni interne |

Per cambiare modalità dopo l'install:
```bash
sed -i 's/LATTICE_COMPLIANCE_MODE=.*/LATTICE_COMPLIANCE_MODE=0/' .env
docker compose --profile whistleblowing up -d
```

## Backup & Restore

### Backup manuale on-demand
```bash
curl -H "X-Lattice-Role: sovereign" \
  https://mycompany.example.com/api/admin/backup/snapshot \
  -o backup-$(date +%Y%m%d).json
```

### Restore su un nuovo server
```bash
# 1. Installa Lattice sul nuovo server
sudo ./install.sh --domain newserver.example.com

# 2. Restore lo snapshot
curl -X POST -H "Content-Type: application/json" \
  -H "X-Lattice-Role: sovereign" \
  -H "X-Lattice-Backup-Confirm: BACKUP_YES" \
  --data @backup-20260616.json \
  https://newserver.example.com/api/admin/backup/restore
```

Il restore importa: blocks, transactions, tenants, LNS, mails, messages,
recovery enrollments, validator/mixnet config. Tempi: ~30s per 10k transazioni.

### Backup automatici orari
Cron in `/etc/cron.hourly/lattice-backup` salva snapshot ogni ora in
`/opt/lattice/backups/`. Rotazione: ultimi 168 file (1 settimana).

## TLS produzione (Let's Encrypt)

```bash
# Stop frontend temporaneamente
docker compose stop frontend

# Ottieni certificato
certbot certonly --standalone -d mycompany.example.com

# Copia nei volumi
cp /etc/letsencrypt/live/mycompany.example.com/fullchain.pem /opt/lattice/certs/server.crt
cp /etc/letsencrypt/live/mycompany.example.com/privkey.pem   /opt/lattice/certs/server.key

# Riavvia
docker compose up -d frontend

# Auto-renewal (cron)
echo "0 3 * * * certbot renew --quiet && docker compose -f /opt/lattice/docker-compose.yml restart frontend" | crontab -
```

## Verifiche post-install

```bash
# 1. Tutti i servizi sono UP?
docker compose ps

# 2. Backend risponde?
curl -fsS https://mycompany.example.com/api/health

# 3. Modalità attiva?
curl -s https://mycompany.example.com/api/config/runtime | jq .edition

# 4. QBFT validators online?
curl -s https://mycompany.example.com/api/qbft/status | jq .live_count
# (deve essere 4/4)
```

## Disaster Recovery (RTO < 1h)

1. **VM nuova** identica per CPU/RAM/disk
2. **Clone repo** e `sudo ./install.sh`
3. **Restore backup** orario più recente (vedi sopra)
4. **DNS swap** verso nuovo IP

Tempi reali misurati: install 4 min + restore 30s = **5 min totali** per chain
da 10k transazioni.

## Supporto

WhatsApp: +39 351 961 8068
