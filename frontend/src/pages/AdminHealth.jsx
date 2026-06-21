import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { PageHeader, SectionPanel, StatPanel } from "@/components/Primitives";
import {
  Activity,
  HardDrive,
  KeyRound,
  ShieldCheck,
  ShieldAlert,
  Cpu,
  Network,
  AlertTriangle,
  RefreshCw,
  Calendar,
  FileKey,
  Bitcoin,
  Anchor,
  Download,
  Upload,
} from "lucide-react";
import { toast } from "sonner";

function fmtBytes(n) {
  if (!Number.isFinite(n)) return "—";
  const u = ["B", "KB", "MB", "GB", "TB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i++; }
  return `${v.toFixed(1)} ${u[i]}`;
}

function StatusBadge({ ok, label }) {
  return (
    <span
      data-testid={`admin-health-badge-${(label || "").toLowerCase().replace(/\s+/g, "-")}`}
      className={`inline-flex items-center gap-1.5 px-2 py-0.5 text-[10px] font-mono-data uppercase tracking-[0.18em] border ${
        ok
          ? "border-emerald-500/40 text-emerald-300 bg-emerald-500/5"
          : "border-red-500/40 text-red-300 bg-red-500/5"
      }`}
    >
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${ok ? "bg-emerald-400" : "bg-red-400"}`} />
      {label}
    </span>
  );
}

export default function AdminHealth() {
  const [data, setData] = useState(null);
  const [tick, setTick] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        setRefreshing(true);
        const r = await api.get("/admin/health/overview");
        if (!cancelled) setData(r.data);
      } catch (e) {
        console.warn(e);
        if (!cancelled) toast.error("Impossibile caricare lo stato del sistema");
      } finally {
        if (!cancelled) setRefreshing(false);
      }
    };
    load();
    const id = setInterval(load, 10_000);
    return () => { cancelled = true; clearInterval(id); };
  }, [tick]);

  const secrets = data?.secrets;
  const license = data?.license;
  const validators = data?.validators;
  const mixnet = data?.mixnet;
  const chain = data?.chain;
  const disk = data?.disk;
  const alerts = data?.alerts || [];
  const ots = data?.ots;
  const [otsAnchors, setOtsAnchors] = useState([]);

  useEffect(() => {
    if (!ots?.enabled) return;
    let cancelled = false;
    (async () => {
      try {
        const r = await api.get("/admin/ots/status");
        if (!cancelled) setOtsAnchors(r.data?.anchors || []);
      } catch (e) {
        console.warn(e);
      }
    })();
    return () => { cancelled = true; };
  }, [tick, ots?.enabled]);

  // Health verdicts
  const validatorOk = validators && !validators.error && validators.quorum_reached;
  const secretsOk = secrets?.unlocked === true;
  const licenseSigned = license?.signed === true;
  const licenseExpiringSoon = (license?.days_remaining ?? 9999) < 30;
  const diskOk = (disk?.used_pct ?? 0) < 85;

  // License quota usage (Iter_31)
  const tenantQuotaPct = (license?.max_tenants && chain?.tenants != null)
    ? Math.round((chain.tenants / license.max_tenants) * 100)
    : null;
  const userQuotaPct = (license?.max_users && chain?.lns_identities != null)
    ? Math.round((chain.lns_identities / license.max_users) * 100)
    : null;
  const tenantQuotaWarning = tenantQuotaPct !== null && tenantQuotaPct >= 95;
  const userQuotaWarning = userQuotaPct !== null && userQuotaPct >= 95;
  const anyQuotaWarning = tenantQuotaWarning || userQuotaWarning;

  const onReloadLicense = async () => {
    try {
      await api.post("/admin/license/reload");
      toast.success("Licenza ricaricata da disco");
      setTick((t) => t + 1);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Reload fallito");
    }
  };

  const onUploadLicense = async (event) => {
    const file = event.target.files?.[0];
    event.target.value = ""; // reset for re-selection
    if (!file) return;
    try {
      const text = await file.text();
      let licenseDoc;
      try {
        licenseDoc = JSON.parse(text);
      } catch {
        toast.error("File non valido: deve essere JSON firmato (.lic)");
        return;
      }
      if (!licenseDoc.signature_hex || !licenseDoc.edition) {
        toast.error("File non valido: manca signature_hex o edition");
        return;
      }
      toast.message(`Verifica firma ML-DSA-65 di ${file.name}…`);
      const r = await api.post("/admin/license/install", { license: licenseDoc });
      const ed = r.data?.status?.edition?.toUpperCase() || "OK";
      toast.success(`Licenza ${ed} installata`);
      setTick((t) => t + 1);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Upload fallito");
    }
  };

  const onCreateAnchor = async () => {
    try {
      toast.message("Submitting anchor to OpenTimestamps…");
      const r = await api.post("/admin/ots/anchor");
      toast.success(`Anchor creato: ${r.data?.anchor?.anchor_id}`);
      setTick((t) => t + 1);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Anchor fallito");
    }
  };

  const onUpgradeAnchor = async (anchorId) => {
    try {
      await api.post(`/admin/ots/upgrade/${anchorId}`);
      toast.success("Proof aggiornato dal calendario");
      setTick((t) => t + 1);
    } catch (e) {
      toast.error(e?.response?.data?.detail || "Upgrade fallito");
    }
  };

  const onDownloadProof = (anchorId) => {
    const url = `${process.env.REACT_APP_BACKEND_URL}/api/admin/ots/anchors/${anchorId}/proof`;
    window.open(url, "_blank");
  };

  return (
    <div data-testid="admin-health-page" className="space-y-8">
      <PageHeader
        eyebrow="SYSADMIN · ONE-PANE"
        title="System Health"
        subtitle="Vista unificata per il manutentore: stato validatori, mixnet, ledger, keystore, licenza, disco e alert attivi."
        right={
          <button
            data-testid="admin-health-refresh-btn"
            onClick={() => setTick((t) => t + 1)}
            className="inline-flex items-center gap-2 px-3 py-2 text-[11px] font-mono-data uppercase tracking-[0.18em] border hairline hover:border-[var(--lattice-gold)] hover:text-white text-[var(--lattice-text-3)]"
          >
            <RefreshCw size={12} className={refreshing ? "animate-spin" : ""} />
            Aggiorna
          </button>
        }
      />

      {/* Top-line stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatPanel
          testId="admin-health-stat-validators"
          icon={Activity}
          label="Validatori"
          value={validators?.error ? "—" : `${validators?.online || 0}/${validators?.total || 0}`}
          sub={validators?.consensus || (validators?.error ? `ERR: ${validators.error}` : "QBFT")}
          accent
        />
        <StatPanel
          testId="admin-health-stat-mixnet"
          icon={Network}
          label="Mixnet"
          value={mixnet?.enabled ? `${mixnet?.online || 0}/${mixnet?.total || 0}` : "OFF"}
          sub={mixnet?.enabled ? "Sphinx · 3 hop" : "Disabilitata · compliance mode"}
        />
        <StatPanel
          testId="admin-health-stat-ledger"
          icon={Cpu}
          label="Ledger"
          value={chain?.blocks ?? "—"}
          sub={`${chain?.transactions ?? 0} tx · ${chain?.tenants ?? 0} tenants · ${chain?.lns_identities ?? 0} LNS`}
        />
        <StatPanel
          testId="admin-health-stat-disk"
          icon={HardDrive}
          label="Disco"
          value={disk ? `${disk.used_pct}%` : "—"}
          sub={disk ? `${fmtBytes(disk.free_bytes)} liberi su ${fmtBytes(disk.total_bytes)}` : "n/a"}
        />
      </div>

      {/* Alerts banner */}
      {alerts.length > 0 ? (
        <div data-testid="admin-health-alerts-banner" className="surface p-4 border-l-2 border-amber-500">
          <div className="flex items-center gap-2 mb-2 text-amber-300">
            <AlertTriangle size={14} />
            <div className="eyebrow !text-amber-300">{alerts.length} alert attivi</div>
          </div>
          <ul className="text-[12px] font-mono-data text-[var(--lattice-text-2)] space-y-1">
            {alerts.map((a, i) => (
              <li key={i} className="flex items-center gap-2">
                <span className={`inline-block w-1.5 h-1.5 rounded-full ${a.severity === "critical" ? "bg-red-400" : "bg-amber-400"}`} />
                <span className="uppercase tracking-[0.12em]">{a.severity}</span>
                <span className="opacity-60">·</span>
                <span>{a.key}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {/* Quota warning banner — fired at ≥95% of license limits */}
      {anyQuotaWarning ? (
        <div data-testid="admin-health-quota-banner" className="surface p-4 border-l-2 border-amber-500 bg-amber-500/5">
          <div className="flex items-center gap-2 mb-2 text-amber-300">
            <AlertTriangle size={14} />
            <div className="eyebrow !text-amber-300">Quota licenza vicino al limite</div>
          </div>
          <ul className="text-[12px] font-mono-data text-[var(--lattice-text-2)] space-y-1">
            {tenantQuotaWarning ? (
              <li data-testid="admin-health-quota-tenants-warning">
                <span className="text-amber-300 uppercase tracking-[0.12em]">tenants</span>
                <span className="opacity-60"> · </span>
                <span className="text-white">{chain.tenants} / {license.max_tenants}</span>
                <span className="opacity-60"> · </span>
                <span className="text-amber-300">{tenantQuotaPct}%</span>
                <span className="text-[var(--lattice-text-3)]"> — il prossimo POST /tenants/register ritornerà HTTP 402</span>
              </li>
            ) : null}
            {userQuotaWarning ? (
              <li data-testid="admin-health-quota-users-warning">
                <span className="text-amber-300 uppercase tracking-[0.12em]">utenti LNS</span>
                <span className="opacity-60"> · </span>
                <span className="text-white">{chain.lns_identities} / {license.max_users}</span>
                <span className="opacity-60"> · </span>
                <span className="text-amber-300">{userQuotaPct}%</span>
                <span className="text-[var(--lattice-text-3)]"> — il prossimo POST /lns/register ritornerà HTTP 402</span>
              </li>
            ) : null}
            <li className="pt-2 text-[var(--lattice-text-3)] italic">
              Carica una licenza con quota superiore per ripristinare la capacità.
            </li>
          </ul>
        </div>
      ) : null}

      {/* Keystore + License */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <SectionPanel
          testId="admin-health-secrets-card"
          eyebrow="AT-REST KEYSTORE"
          title="Master Key Manager"
          subtitle="Cifratura at-rest delle chiavi ML-DSA dei validatori."
          right={<StatusBadge ok={secretsOk} label={secretsOk ? "UNLOCKED" : "LOCKED"} />}
        >
          <div className="px-5 py-4 space-y-3 text-[12px]">
            <div className="flex justify-between">
              <span className="text-[var(--lattice-text-3)] uppercase tracking-[0.14em] font-mono-data">Mode</span>
              <span data-testid="admin-health-secrets-mode" className="font-mono-data text-white">{secrets?.mode || "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--lattice-text-3)] uppercase tracking-[0.14em] font-mono-data">KDF</span>
              <span className="font-mono-data text-white">{secrets?.kdf || "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--lattice-text-3)] uppercase tracking-[0.14em] font-mono-data">Argon2 mem</span>
              <span className="font-mono-data text-white">{secrets?.kdf_params?.memory_cost_kb} KB · t={secrets?.kdf_params?.time_cost} · p={secrets?.kdf_params?.parallelism}</span>
            </div>
            {secrets?.locked_reason ? (
              <div className="mt-2 p-3 bg-red-500/5 border border-red-500/30 text-red-200 text-[11px] font-mono-data">
                {secrets.locked_reason}
              </div>
            ) : null}
          </div>
        </SectionPanel>

        <SectionPanel
          testId="admin-health-license-card"
          eyebrow="LICENZA"
          title={license?.edition ? license.edition.toUpperCase() : "—"}
          subtitle={license?.tenant_name || "Community edition"}
          right={
            <div className="flex items-center gap-2">
              <StatusBadge ok={licenseSigned} label={licenseSigned ? "FIRMATA" : "COMMUNITY"} />
              <label
                data-testid="admin-health-license-upload-label"
                className="inline-flex items-center gap-1.5 px-2 py-1 text-[10px] font-mono-data uppercase tracking-[0.18em] border border-[var(--lattice-gold)]/40 text-[var(--lattice-gold)] hover:bg-[var(--lattice-gold)]/10 cursor-pointer"
                title="Carica un file .lic firmato dal vendor"
              >
                <Upload size={11} /> Upload .lic
                <input
                  data-testid="admin-health-license-upload-input"
                  type="file"
                  accept=".lic,application/json"
                  className="hidden"
                  onChange={onUploadLicense}
                />
              </label>
              <button
                data-testid="admin-health-license-reload-btn"
                onClick={onReloadLicense}
                className="inline-flex items-center gap-1.5 px-2 py-1 text-[10px] font-mono-data uppercase tracking-[0.18em] border hairline hover:border-[var(--lattice-gold)] hover:text-white text-[var(--lattice-text-3)]"
              >
                <FileKey size={11} /> Reload
              </button>
            </div>
          }
        >
          <div className="px-5 py-4 space-y-3 text-[12px]">
            <div className="flex justify-between">
              <span className="text-[var(--lattice-text-3)] uppercase tracking-[0.14em] font-mono-data">License ID</span>
              <span className="font-mono-data text-white">{license?.license_id || "—"}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--lattice-text-3)] uppercase tracking-[0.14em] font-mono-data">Quota tenants</span>
              <span className={`font-mono-data ${tenantQuotaWarning ? "text-amber-300" : "text-white"}`}>
                {chain?.tenants != null && license?.max_tenants != null
                  ? `${chain.tenants} / ${license.max_tenants} (${tenantQuotaPct}%)`
                  : license?.max_tenants ?? "∞"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--lattice-text-3)] uppercase tracking-[0.14em] font-mono-data">Quota utenti</span>
              <span className={`font-mono-data ${userQuotaWarning ? "text-amber-300" : "text-white"}`}>
                {chain?.lns_identities != null && license?.max_users != null
                  ? `${chain.lns_identities} / ${license.max_users} (${userQuotaPct}%)`
                  : license?.max_users ?? "∞"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--lattice-text-3)] uppercase tracking-[0.14em] font-mono-data flex items-center gap-1.5">
                <Calendar size={11} /> Scadenza
              </span>
              <span className={`font-mono-data ${licenseExpiringSoon ? "text-amber-300" : "text-white"}`}>
                {license?.valid_until ? `${license.valid_until.slice(0, 10)} · ${license.days_remaining}g` : "Perpetua"}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--lattice-text-3)] uppercase tracking-[0.14em] font-mono-data flex items-center gap-1.5">
                <KeyRound size={11} /> Vendor FPR
              </span>
              <span className="font-mono-data text-[var(--lattice-text-2)]">{license?.vendor_pubkey_fpr || "—"}</span>
            </div>
            {license?.features?.length ? (
              <div className="pt-2">
                <div className="text-[var(--lattice-text-3)] uppercase tracking-[0.14em] font-mono-data mb-2">Features</div>
                <div className="flex flex-wrap gap-1.5">
                  {license.features.map((f) => (
                    <span key={f} className="px-2 py-0.5 text-[10px] font-mono-data uppercase tracking-[0.12em] border border-[var(--lattice-gold)]/30 text-[var(--lattice-gold)]/90 bg-[var(--lattice-gold)]/5">{f}</span>
                  ))}
                </div>
              </div>
            ) : null}
            {license?.last_error ? (
              <div className="mt-2 p-3 bg-red-500/5 border border-red-500/30 text-red-200 text-[11px] font-mono-data">
                {license.last_error}
              </div>
            ) : null}
          </div>
        </SectionPanel>
      </div>

      {/* Validators detail table */}
      <SectionPanel
        testId="admin-health-validators-table"
        eyebrow="QBFT"
        title="Validatori"
        subtitle={validators?.consensus || "—"}
        right={<StatusBadge ok={validatorOk} label={validatorOk ? "QUORUM OK" : "QUORUM PERSO"} />}
      >
        <div className="px-5 py-2 overflow-x-auto">
          <table className="w-full text-[12px] font-mono-data">
            <thead className="border-b hairline">
              <tr className="text-left text-[var(--lattice-text-3)]">
                <th className="py-2 pr-4 uppercase tracking-[0.14em]">ID</th>
                <th className="py-2 pr-4 uppercase tracking-[0.14em]">Endpoint</th>
                <th className="py-2 pr-4 uppercase tracking-[0.14em]">Live</th>
                <th className="py-2 pr-4 uppercase tracking-[0.14em]">Firme</th>
                <th className="py-2 pr-4 uppercase tracking-[0.14em]">FPR</th>
              </tr>
            </thead>
            <tbody>
              {(validators?.nodes || []).map((n) => (
                <tr key={n.validator_id} className="border-b hairline/40">
                  <td className="py-2 pr-4 text-white">{n.validator_id}</td>
                  <td className="py-2 pr-4 text-[var(--lattice-text-2)]">{n.endpoint}</td>
                  <td className="py-2 pr-4">
                    {n.live ? <ShieldCheck size={12} className="text-emerald-400" /> : <ShieldAlert size={12} className="text-red-400" />}
                  </td>
                  <td className="py-2 pr-4 text-white">{n.signed_total ?? 0}</td>
                  <td className="py-2 pr-4 text-[var(--lattice-text-3)]" title={n.pk_fingerprint}>
                    {n.pk_fingerprint ? `${n.pk_fingerprint.slice(0, 8)}…` : "—"}
                  </td>
                </tr>
              ))}
              {(!validators?.nodes || validators.nodes.length === 0) ? (
                <tr><td colSpan={5} className="py-6 text-center text-[var(--lattice-text-4)] uppercase tracking-[0.18em]">no data</td></tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </SectionPanel>

      {/* OpenTimestamps anchor card */}
      <SectionPanel
        testId="admin-health-ots-card"
        eyebrow="OPENTIMESTAMPS"
        title="Bitcoin Anchor"
        subtitle={
          ots?.enabled
            ? "Ancora la testa del ledger nel prossimo blocco Bitcoin via OpenTimestamps."
            : "Disabilitato — imposta LATTICE_OTS_ENABLED=1 nel .env per attivare."
        }
        right={
          ots?.enabled ? (
            <div className="flex items-center gap-2">
              <StatusBadge ok={true} label={`${ots?.anchors_total || 0} ANCHORS`} />
              <button
                data-testid="admin-health-ots-create-btn"
                onClick={onCreateAnchor}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-mono-data uppercase tracking-[0.18em] border border-[var(--lattice-gold)]/40 text-[var(--lattice-gold)] hover:bg-[var(--lattice-gold)]/10"
              >
                <Anchor size={11} /> Nuovo anchor
              </button>
            </div>
          ) : (
            <StatusBadge ok={false} label="OFF" />
          )
        }
      >
        <div className="px-5 py-4 space-y-3 text-[12px]">
          {ots?.enabled ? (
            <>
              <div className="flex justify-between">
                <span className="text-[var(--lattice-text-3)] uppercase tracking-[0.14em] font-mono-data">Calendars</span>
                <span className="font-mono-data text-[var(--lattice-text-2)] text-right">
                  {(ots?.calendars || []).length} federated
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--lattice-text-3)] uppercase tracking-[0.14em] font-mono-data flex items-center gap-1.5">
                  <Bitcoin size={11} /> BTC attested
                </span>
                <span className="font-mono-data text-white">{ots?.btc_attested ?? 0} / {ots?.anchors_total ?? 0}</span>
              </div>
              <div className="pt-2">
                <div className="text-[var(--lattice-text-3)] uppercase tracking-[0.14em] font-mono-data mb-2">Ultimi ancoraggi</div>
                <div className="overflow-x-auto">
                  <table className="w-full text-[11px] font-mono-data">
                    <thead className="border-b hairline">
                      <tr className="text-left text-[var(--lattice-text-3)]">
                        <th className="py-2 pr-3 uppercase tracking-[0.14em]">ID</th>
                        <th className="py-2 pr-3 uppercase tracking-[0.14em]">Block</th>
                        <th className="py-2 pr-3 uppercase tracking-[0.14em]">Digest</th>
                        <th className="py-2 pr-3 uppercase tracking-[0.14em]">BTC</th>
                        <th className="py-2 pr-3 uppercase tracking-[0.14em]">Created</th>
                        <th className="py-2 uppercase tracking-[0.14em]"></th>
                      </tr>
                    </thead>
                    <tbody>
                      {otsAnchors.map((a) => (
                        <tr key={a.anchor_id} className="border-b hairline/40">
                          <td className="py-2 pr-3 text-white" title={a.anchor_id}>
                            {a.anchor_id.slice(-12)}
                          </td>
                          <td className="py-2 pr-3 text-[var(--lattice-text-2)]">#{a.block_index}</td>
                          <td className="py-2 pr-3 text-[var(--lattice-text-3)]" title={a.digest_hex}>
                            {a.digest_hex.slice(0, 16)}…
                          </td>
                          <td className="py-2 pr-3">
                            {a.btc_attested ? (
                              <Bitcoin size={12} className="text-amber-400" />
                            ) : (
                              <span className="text-[10px] text-[var(--lattice-text-4)] uppercase tracking-[0.14em]">pending</span>
                            )}
                          </td>
                          <td className="py-2 pr-3 text-[var(--lattice-text-3)]">{a.created_at?.slice(0, 16).replace("T", " ")}</td>
                          <td className="py-2 flex items-center gap-1.5">
                            <button
                              data-testid={`admin-health-ots-upgrade-${a.anchor_id}`}
                              onClick={() => onUpgradeAnchor(a.anchor_id)}
                              className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] border hairline hover:border-[var(--lattice-gold)] text-[var(--lattice-text-3)] hover:text-white uppercase tracking-[0.14em]"
                              title="Re-fetch proof from calendar"
                            >
                              <RefreshCw size={9} />
                            </button>
                            <button
                              data-testid={`admin-health-ots-download-${a.anchor_id}`}
                              onClick={() => onDownloadProof(a.anchor_id)}
                              className="inline-flex items-center gap-1 px-1.5 py-0.5 text-[10px] border hairline hover:border-[var(--lattice-gold)] text-[var(--lattice-text-3)] hover:text-white uppercase tracking-[0.14em]"
                              title="Download .ots proof"
                            >
                              <Download size={9} />
                            </button>
                          </td>
                        </tr>
                      ))}
                      {otsAnchors.length === 0 ? (
                        <tr><td colSpan={6} className="py-6 text-center text-[var(--lattice-text-4)] uppercase tracking-[0.18em]">no anchors yet</td></tr>
                      ) : null}
                    </tbody>
                  </table>
                </div>
              </div>
              <div className="text-[10px] text-[var(--lattice-text-4)] italic pt-1">
                I file .ots possono essere verificati con il CLI ufficiale: <span className="font-mono-data text-[var(--lattice-text-2)]">ots verify &lt;file&gt;.ots</span>
              </div>
            </>
          ) : (
            <div className="text-[var(--lattice-text-3)] text-center py-4 italic">
              Per attivare l&apos;ancoraggio Bitcoin, imposta <span className="font-mono-data text-[var(--lattice-gold)]">LATTICE_OTS_ENABLED=1</span> in <span className="font-mono-data">backend/.env</span> e riavvia.
            </div>
          )}
        </div>
      </SectionPanel>

      <div className="text-[10px] font-mono-data text-[var(--lattice-text-4)] uppercase tracking-[0.18em] text-center pt-4">
        Refresh automatico ogni 10s · {data?.timestamp?.slice(11, 19) || "—"} UTC · chain={data?.chain_id || "—"}
      </div>
    </div>
  );
}
