#!/usr/bin/env python3
"""Genera le immagini del libro LATTICE."""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as patches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
from pathlib import Path

OUT = Path("/app/memory/book_img")
OUT.mkdir(parents=True, exist_ok=True)

# Palette Lattice
NAVY = '#0A0F1E'
GOLD = '#D4AF37'
CREAM = '#F8F4E8'
GREY = '#555555'
LIGHT = '#E8E8E8'

# ============================================================
# FIG 0 — Cover
# ============================================================
fig, ax = plt.subplots(figsize=(8, 12), dpi=200)
ax.set_xlim(0, 10); ax.set_ylim(0, 15); ax.axis('off')
ax.set_facecolor(NAVY)
fig.patch.set_facecolor(NAVY)
# Lattice pattern decoration
import numpy as np
for i in range(8):
    for j in range(12):
        x, y = i*1.3+0.6, j*1.2+0.3
        if (i+j) % 3 == 0:
            ax.plot(x, y, 'o', color=GOLD, markersize=3, alpha=0.4)
        for dx, dy in [(1.3,0),(0,1.2),(1.3,1.2)]:
            if i*1.3+0.6+dx < 10 and j*1.2+0.3+dy < 15:
                ax.plot([x, x+dx], [y, y+dy], '-', color=GOLD, linewidth=0.4, alpha=0.2)
# Title
ax.text(5, 9.5, 'LATTICE', fontsize=78, color=GOLD, ha='center', weight='bold', family='serif')
ax.text(5, 8.2, 'La cybersicurezza sovrana', fontsize=20, color=CREAM, ha='center', style='italic', family='serif')
ax.text(5, 7.5, "dell'Italia post-quantum", fontsize=20, color=CREAM, ha='center', style='italic', family='serif')
# Subtitle
ax.text(5, 5.8, 'Architettura, crittografia ML-DSA-65', fontsize=11, color=CREAM, ha='center', family='serif')
ax.text(5, 5.3, 'e infrastruttura on-premise', fontsize=11, color=CREAM, ha='center', family='serif')
ax.text(5, 4.8, "nell'era della minaccia quantistica", fontsize=11, color=CREAM, ha='center', family='serif')
# Bottom mark
ax.plot([3.5, 6.5], [2.5, 2.5], '-', color=GOLD, linewidth=1.5)
ax.text(5, 1.8, 'PRIMA EDIZIONE · 2026', fontsize=10, color=GOLD, ha='center', weight='bold', family='sans-serif')
plt.savefig(OUT/'00_cover.png', bbox_inches='tight', dpi=200, facecolor=NAVY)
plt.close()

# ============================================================
# FIG 1.1 — Q-Day timeline
# ============================================================
fig, ax = plt.subplots(figsize=(10, 5), dpi=200)
ax.set_xlim(2020, 2040); ax.set_ylim(-1, 6); ax.axis('off')
# Timeline line
ax.plot([2020, 2040], [0, 0], '-', color=NAVY, linewidth=3)
# Events
events = [
    (2024, 4.5, "NIST FIPS 203/204/205\npubblicati", GOLD),
    (2025, 2.5, "NIS2 + DORA\nin vigore", NAVY),
    (2026, 3.8, "Inizio migrazione\nraccomandata", NAVY),
    (2030, 5, "Q-Day\nottimistico", '#cc0000'),
    (2034, 4, "Q-Day\ncentrale", '#cc0000'),
    (2040, 3, "Q-Day\npessimistico", '#cc0000'),
]
for year, height, label, color in events:
    ax.plot([year, year], [0, height], '--', color=color, linewidth=1)
    ax.plot(year, 0, 'o', color=color, markersize=10)
    ax.text(year, height + 0.2, label, ha='center', fontsize=9, color=color, weight='bold')
    ax.text(year, -0.4, str(year), ha='center', fontsize=10, color=NAVY, weight='bold')
ax.text(2030, -0.95, 'Finestra di azione: 2026 → 2030', ha='center', fontsize=11,
        color=GOLD, weight='bold', style='italic')
ax.set_title("Fig. 1.1 — Timeline Q-Day e finestra di migrazione PQC",
             fontsize=12, color=NAVY, weight='bold', pad=20)
plt.savefig(OUT/'fig_1_1_qday_timeline.png', bbox_inches='tight', dpi=200, facecolor='white')
plt.close()

# ============================================================
# FIG 4.1 — 6 dimensioni della sovranità
# ============================================================
fig, ax = plt.subplots(figsize=(10, 7), dpi=200)
ax.set_xlim(0, 10); ax.set_ylim(0, 7); ax.axis('off')
dims = [
    (1.5, 5.2, "CODICE", "Ispezionabile,\nmodificabile,\nredistribuibile"),
    (5, 5.2, "DATI", "Localizzazione, controllo,\nexport, cancellazione\nverificabile"),
    (8.5, 5.2, "CHIAVI", "Generazione e\ncustodia esclusiva\ndel titolare"),
    (1.5, 1.8, "INFRASTRUTTURA", "Hardware,\naccesso fisico,\nispezione"),
    (5, 1.8, "AGGIORNAMENTI", "Tempi, contenuti,\nautorizzazione\nesplicita"),
    (8.5, 1.8, "FORNITURA", "SBOM completo,\nbuild riproducibili,\ndipendenze minime"),
]
for x, y, title, desc in dims:
    box = FancyBboxPatch((x-1.4, y-1.1), 2.8, 2.2,
                         boxstyle="round,pad=0.05", linewidth=2,
                         edgecolor=GOLD, facecolor=CREAM)
    ax.add_patch(box)
    ax.text(x, y+0.6, title, ha='center', fontsize=11, weight='bold', color=NAVY)
    ax.plot([x-0.8, x+0.8], [y+0.3, y+0.3], '-', color=GOLD, linewidth=1)
    ax.text(x, y-0.3, desc, ha='center', fontsize=9, color=GREY)
ax.set_title("Fig. 4.1 — Le sei dimensioni della sovranità software",
             fontsize=13, color=NAVY, weight='bold', pad=15)
plt.savefig(OUT/'fig_4_1_sovranita.png', bbox_inches='tight', dpi=200, facecolor='white')
plt.close()

# ============================================================
# FIG 7.1 — Architettura Lattice
# ============================================================
fig, ax = plt.subplots(figsize=(11, 9), dpi=200)
ax.set_xlim(0, 11); ax.set_ylim(0, 11); ax.axis('off')

def box(x, y, w, h, text, color, edge=NAVY, fontsize=10, weight='bold', text_color=None):
    b = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                       linewidth=1.8, edgecolor=edge, facecolor=color)
    ax.add_patch(b)
    ax.text(x+w/2, y+h/2, text, ha='center', va='center',
            fontsize=fontsize, weight=weight,
            color=text_color or (NAVY if color != NAVY else CREAM))

def arrow(x1, y1, x2, y2):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=GOLD, lw=1.8))

# Layer 5 — Tenants
for i, t in enumerate(['Banca', 'Comune', 'Studio Legale', 'ASL']):
    box(0.4 + i*2.6, 9.5, 2.2, 0.8, f"Tenant {chr(65+i)}\n{t}", LIGHT, fontsize=8)
# Layer 4 — Gateway
box(2, 7.8, 7, 1, "GATEWAY (FastAPI + WASM)\nJWT · PQC challenge-response · RBAC", CREAM, edge=GOLD, fontsize=10)
# Arrows from tenants to gateway
for i in range(4):
    arrow(1.5 + i*2.6, 9.4, 5.5, 8.9)
# Layer 3 — Modules
box(0.3, 5.8, 2.4, 1.3, "CERTIFY\nPEC E2E\nML-DSA + receipt", '#F0E6CC', fontsize=9)
box(3, 5.8, 2.4, 1.3, "PULSE\nchat sicura\nPQXDH + Ratchet", '#F0E6CC', fontsize=9)
box(5.7, 5.8, 2.4, 1.3, "LNS\nname service\nkeystore", '#F0E6CC', fontsize=9)
box(8.4, 5.8, 2.4, 1.3, "AUDIT\nlog chain\nSHA3 + OTS", '#F0E6CC', fontsize=9)
# Arrows from gateway to modules
for x in [1.5, 4.2, 6.9, 9.6]:
    arrow(5.5, 7.7, x, 7.2)
# Layer 2 — Mixnet
box(2, 4.1, 4, 1, "LOOPIX MIXNET 3-hop\nZK-RLN rate limiting", '#E6D9A3', fontsize=10)
arrow(1.5, 5.7, 3, 5.2)
arrow(4.2, 5.7, 4, 5.2)
# Layer 1 — QBFT
box(0.5, 2.5, 10, 1.1, "QBFT CONSENSUS · 4 validatori indipendenti\nfinalità 420ms · ML-DSA-65 per ogni blocco",
    NAVY, edge=GOLD, fontsize=10, text_color=CREAM)
arrow(4, 4, 4, 3.7); arrow(7, 5.7, 7, 3.7); arrow(10, 5.7, 8, 3.7)
# Layer 0 — Storage + Anchor
box(0.5, 1.2, 4.8, 0.9, "MongoDB\nAES-256-GCM at-rest · Argon2id master keys", LIGHT, fontsize=9)
box(5.7, 1.2, 4.8, 0.9, "OpenTimestamps ANCHOR\nBitcoin blockchain · ogni 6 ore", '#FFE4A1', edge=GOLD, fontsize=9)
arrow(3, 2.4, 3, 2.2); arrow(8, 2.4, 8, 2.2)
# Bottom legend
ax.text(5.5, 0.4, "Lattice Network — 5 colonne · 7 layer di difesa in profondità",
        ha='center', fontsize=10, style='italic', color=GOLD, weight='bold')
ax.set_title("Fig. 7.1 — Architettura Lattice Network",
             fontsize=14, color=NAVY, weight='bold', pad=15)
plt.savefig(OUT/'fig_7_1_architettura.png', bbox_inches='tight', dpi=200, facecolor='white')
plt.close()

# ============================================================
# FIG 7.2 — Architettura Rust + Python + WASM
# ============================================================
fig, ax = plt.subplots(figsize=(9, 9), dpi=200)
ax.set_xlim(0, 10); ax.set_ylim(0, 10); ax.axis('off')

box(1.5, 8.2, 7, 1.2, "STRATO 3 — INTERFACCIA UTENTE\nReact SPA · solo UI, nessuna crittografia",
    LIGHT, fontsize=10)
box(1.5, 6.3, 7, 1.3, "STRATO 2 — CRITTO CLIENT-SIDE\n🦀 RUST → WebAssembly (lattice-wasm)\nML-DSA-65 sign nel browser",
    '#FFE4A1', edge=GOLD, fontsize=10)
box(1.5, 4.4, 7, 1.3, "STRATO 1 — GATEWAY E ORCHESTRAZIONE\n🐍 Python FastAPI · routing, DB, JWT, audit",
    '#E0F4E0', fontsize=10)
box(1.5, 1.6, 7, 2.3, "STRATO 0 — PRIMITIVE CRITTOGRAFICHE (il cuore)\n🦀 RUST CARGO WORKSPACE · 10 crate · ~1.500 righe\nlattice-crypto · lattice-node · pulse-protocol\npulse-ratchet · lattice-zk-rln · lattice-mixnet\nlattice-py (PyO3) · lattice-wasm",
    NAVY, edge=GOLD, fontsize=10, text_color=CREAM)
# Arrows
arrow(5, 8.1, 5, 7.7)
arrow(5, 6.2, 5, 5.8)
arrow(5, 4.3, 5, 4.0)
# Side note
ax.text(0.6, 7, "browser", rotation=90, fontsize=9, color=GREY, va='center')
ax.text(0.6, 5, "server", rotation=90, fontsize=9, color=GREY, va='center')
ax.text(0.6, 2.8, "native", rotation=90, fontsize=9, color=GREY, va='center')
ax.set_title("Fig. 7.2 — Architettura ibrida Rust + Python + WASM",
             fontsize=13, color=NAVY, weight='bold', pad=15)
plt.savefig(OUT/'fig_7_2_rust_stack.png', bbox_inches='tight', dpi=200, facecolor='white')
plt.close()

# ============================================================
# FIG 8.1 — Confronto algoritmi
# ============================================================
fig, ax = plt.subplots(figsize=(10, 5), dpi=200)
algos = ['RSA-2048', 'ECDSA-P256', 'Ed25519', 'ML-DSA-65']
pk_sizes = [256, 64, 32, 1952]
sig_sizes = [256, 64, 64, 3309]
quantum_safe = ['NO', 'NO', 'NO', 'SÌ']
colors = ['#cc6677', '#ddaa44', '#88aabb', GOLD]
x = np.arange(len(algos))
width = 0.35
ax.bar(x - width/2, pk_sizes, width, label='Chiave pubblica (byte)', color=NAVY, alpha=0.85)
ax.bar(x + width/2, sig_sizes, width, label='Firma (byte)', color=GOLD)
ax.set_yscale('log')
ax.set_xticks(x); ax.set_xticklabels(algos, fontsize=11, weight='bold')
ax.set_ylabel('Byte (scala logaritmica)', fontsize=10)
for i, qs in enumerate(quantum_safe):
    color_text = '#00aa00' if qs == 'SÌ' else '#cc0000'
    ax.text(i, 5500, f'Quantum-safe: {qs}', ha='center', fontsize=10,
            weight='bold', color=color_text)
ax.legend(loc='upper left', fontsize=10)
ax.set_title("Fig. 8.1 — Confronto dimensioni chiavi e firme tra algoritmi",
             fontsize=13, color=NAVY, weight='bold', pad=15)
ax.grid(True, alpha=0.3, axis='y')
plt.tight_layout()
plt.savefig(OUT/'fig_8_1_confronto_algo.png', bbox_inches='tight', dpi=200, facecolor='white')
plt.close()

# ============================================================
# FIG 9.1 — QBFT consensus flow
# ============================================================
fig, ax = plt.subplots(figsize=(10, 6), dpi=200)
ax.set_xlim(0, 10); ax.set_ylim(0, 7); ax.axis('off')
# 4 validators arranged in square
val_pos = [(2.5, 5), (7.5, 5), (2.5, 2), (7.5, 2)]
for i, (x, y) in enumerate(val_pos):
    color = GOLD if i == 0 else CREAM
    circle = plt.Circle((x, y), 0.7, color=color, ec=NAVY, linewidth=2)
    ax.add_patch(circle)
    ax.text(x, y, f"VAL\n0{i+1}", ha='center', va='center', fontsize=10, weight='bold', color=NAVY)
    if i == 0:
        ax.text(x, y+1.1, "PRIMARY", ha='center', fontsize=9, color=GOLD, weight='bold')
# Arrows between validators
for i in range(4):
    for j in range(4):
        if i != j:
            x1, y1 = val_pos[i]; x2, y2 = val_pos[j]
            dx = x2-x1; dy = y2-y1
            d = (dx**2+dy**2)**0.5
            sx, sy = x1 + 0.7*dx/d, y1 + 0.7*dy/d
            ex, ey = x2 - 0.7*dx/d, y2 - 0.7*dy/d
            ax.annotate('', xy=(ex, ey), xytext=(sx, sy),
                        arrowprops=dict(arrowstyle='->', color=GOLD, lw=0.6, alpha=0.5))
# Center
ax.text(5, 3.5, "BLOCCO\nfinalizzato", ha='center', va='center', fontsize=11,
        weight='bold', color=NAVY,
        bbox=dict(boxstyle="round,pad=0.5", fc=CREAM, ec=GOLD, lw=2))
# Footer text
ax.text(5, 0.5, "Finalità deterministica: 3 firme ML-DSA-65 su 4 → blocco confermato in ~420 ms",
        ha='center', fontsize=10, color=NAVY, style='italic', weight='bold')
ax.set_title("Fig. 9.1 — Consenso QBFT: 4 validatori indipendenti",
             fontsize=13, color=NAVY, weight='bold', pad=15)
plt.savefig(OUT/'fig_9_1_qbft.png', bbox_inches='tight', dpi=200, facecolor='white')
plt.close()

# ============================================================
# FIG 9.2 — Loopix mixnet
# ============================================================
fig, ax = plt.subplots(figsize=(11, 5), dpi=200)
ax.set_xlim(0, 12); ax.set_ylim(0, 5); ax.axis('off')
# Alice
ax.add_patch(plt.Circle((0.8, 2.5), 0.5, color=CREAM, ec=NAVY, lw=2))
ax.text(0.8, 2.5, "Alice", ha='center', va='center', fontsize=10, weight='bold')
# Mixnet layers
for layer in range(3):
    x = 3 + layer * 2.5
    for row in range(2):
        y = 1.5 + row * 2
        ax.add_patch(plt.Circle((x, y), 0.4, color=GOLD if (layer+row)%2==0 else CREAM,
                                ec=NAVY, lw=1.5))
        ax.text(x, y, f"M{layer}.{row+1}", ha='center', va='center', fontsize=8)
    ax.text(x, 0.3, f"Layer {layer}", ha='center', fontsize=10, color=GREY, weight='bold')
# Bob
ax.add_patch(plt.Circle((11, 2.5), 0.5, color=CREAM, ec=NAVY, lw=2))
ax.text(11, 2.5, "Bob", ha='center', va='center', fontsize=10, weight='bold')
# Path highlighted
path = [(0.8, 2.5), (3, 1.5), (5.5, 3.5), (8, 1.5), (11, 2.5)]
for i in range(len(path)-1):
    x1, y1 = path[i]; x2, y2 = path[i+1]
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle='->', color=GOLD, lw=2.5))
ax.text(6, 4.5, "Path 3-hop attraverso 3 layer indipendenti", ha='center',
        fontsize=11, color=NAVY, weight='bold')
ax.text(6, 0.7, "Ogni hop introduce delay casuale · onion encryption a strati",
        ha='center', fontsize=9, color=GREY, style='italic')
ax.set_title("Fig. 9.2 — Loopix Mixnet: 3 hop per nascondere i metadati",
             fontsize=13, color=NAVY, weight='bold', pad=15)
plt.savefig(OUT/'fig_9_2_loopix.png', bbox_inches='tight', dpi=200, facecolor='white')
plt.close()

# ============================================================
# FIG 10.1 — Confronto PEC vs Certify
# ============================================================
fig, ax = plt.subplots(figsize=(10, 7), dpi=200)
ax.set_xlim(0, 10); ax.set_ylim(0, 9); ax.axis('off')
features = [
    ('Operatore intermediario', 'Sì, privato', 'NO, self-hosted'),
    ('Cifratura end-to-end', 'No', 'Sì, E2E'),
    ('Firme digitali', 'RSA-2048 / SHA-256', 'ML-DSA-65 / SHA3-512'),
    ('Resistente al quantum', 'NO', 'SÌ'),
    ('Dipendenza dal gestore', 'Critica', 'Nessuna'),
    ('Anchoring on-chain', 'No', 'Sì (QBFT + Bitcoin)'),
    ('Verifica indipendente 30 anni', 'Difficile', 'Banale'),
]
ax.text(2.5, 8.3, 'PEC tradizionale', ha='center', fontsize=13, weight='bold', color='#cc0000')
ax.text(7.5, 8.3, 'Lattice Certify', ha='center', fontsize=13, weight='bold', color=GOLD)
ax.plot([0.2, 9.8], [7.9, 7.9], '-', color=NAVY, lw=1.5)
for i, (feat, pec, cert) in enumerate(features):
    y = 7.3 - i * 0.95
    ax.text(0.3, y, feat, fontsize=9.5, color=NAVY, weight='bold', va='center')
    ax.text(4, y, pec, fontsize=9.5, color='#cc0000', ha='center', va='center')
    ax.text(8, y, cert, fontsize=9.5, color='#008833', ha='center', va='center', weight='bold')
    if i < len(features)-1:
        ax.plot([0.2, 9.8], [y-0.5, y-0.5], '-', color=LIGHT, lw=0.5)
ax.set_title("Fig. 10.1 — Confronto PEC tradizionale vs Lattice Certify",
             fontsize=13, color=NAVY, weight='bold', pad=15)
plt.savefig(OUT/'fig_10_1_pec_vs_certify.png', bbox_inches='tight', dpi=200, facecolor='white')
plt.close()

# ============================================================
# FIG 13.1 — ROI qualitativo (percentuali relative, no importi)
# ============================================================
fig, ax = plt.subplots(figsize=(10, 5), dpi=200)
cases = ['Banca top-10', 'Comune capoluogo', 'Studio Legale', 'ASL']
# Indici relativi 0-100 (alto = beneficio maggiore)
direct_saving = [85, 30, 55, 60]
risk_avoided  = [90, 75, 80, 95]
new_business  = [70, 10, 90, 20]
x = np.arange(len(cases)); width = 0.27
ax.bar(x - width, direct_saving, width, label='Risparmio diretto (qualitativo)', color=GOLD)
ax.bar(x,         risk_avoided,   width, label='Rischio evitato (qualitativo)', color=NAVY)
ax.bar(x + width, new_business,   width, label='Nuovo business / valore aggiunto', color='#888888')
ax.set_xticks(x); ax.set_xticklabels(cases, fontsize=10, weight='bold')
ax.set_ylabel('Indice di beneficio (scala qualitativa 0-100)')
ax.set_ylim(0, 105)
ax.legend(fontsize=9, loc='upper right')
ax.grid(True, alpha=0.3, axis='y')
ax.set_title("Fig. 13.1 — Ritorno relativo dei 4 casi d'uso (indici qualitativi)",
             fontsize=12, color=NAVY, weight='bold', pad=15)
# Disclaimer
fig.text(0.5, -0.02, "I valori sono indici qualitativi relativi tra i casi · gli importi assoluti dipendono dal listino vigente",
         ha='center', fontsize=8, style='italic', color=GREY)
plt.tight_layout()
plt.savefig(OUT/'fig_13_1_roi.png', bbox_inches='tight', dpi=200, facecolor='white')
plt.close()

# ============================================================
# FIG E — Manifesto Lattice (pagina finale)
# ============================================================
fig, ax = plt.subplots(figsize=(8, 11), dpi=200)
ax.set_xlim(0, 10); ax.set_ylim(0, 14); ax.axis('off')
ax.set_facecolor(CREAM); fig.patch.set_facecolor(CREAM)
ax.text(5, 13, 'IL MANIFESTO LATTICE', ha='center', fontsize=22, weight='bold', color=NAVY, family='serif')
ax.plot([3, 7], [12.5, 12.5], '-', color=GOLD, lw=2)
ax.text(5, 12.1, '12 principi per la sovranità digitale italiana', ha='center', fontsize=11,
        style='italic', color=GREY, family='serif')
principles = [
    "La crittografia è un diritto fondamentale.",
    "La sovranità si misura in chi possiede le chiavi.",
    "Il codice deve essere ispezionabile sempre.",
    "I dati restano dove nasce la loro responsabilità.",
    "Le prove crittografiche devono essere valide 30+ anni.",
    "Nessuno standard è inviolabile: usa NIST e ISO.",
    "Il vendor lock-in è incompatibile con la sovranità.",
    "I metadati sono dati: meritano la stessa protezione.",
    "Nessuna terza parte legga ciò che non le appartiene.",
    "La compliance è il pavimento, non il soffitto.",
    "La velocità di adozione è una vulnerabilità.",
    "L'autosovranità italiana è la sovranità di domani."
]
for i, p in enumerate(principles):
    y = 10.8 - i * 0.78
    ax.text(0.5, y, f"{i+1:>2}.", fontsize=12, color=GOLD, weight='bold', family='serif')
    ax.text(1.3, y, p, fontsize=10.5, color=NAVY, family='serif', va='center')
ax.plot([3, 7], [0.8, 0.8], '-', color=GOLD, lw=1)
ax.text(5, 0.3, 'LATTICE NETWORK', ha='center', fontsize=10, weight='bold', color=GOLD, family='sans-serif')
plt.savefig(OUT/'fig_E_manifesto.png', bbox_inches='tight', dpi=200, facecolor=CREAM)
plt.close()

print("OK — generate 10 immagini:")
import os
for f in sorted(OUT.iterdir()):
    print(f"  {f.name:35s} {os.path.getsize(f)//1024:>4d} KB")
