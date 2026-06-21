import { FileText, Image as ImageIcon, Film, Music, FileArchive, FileSpreadsheet, Presentation, Download } from "lucide-react";
import { api } from "@/lib/api";

const REACT_APP_BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

function iconFor(mime, filename) {
  if (!mime) mime = "";
  if (mime.startsWith("image/")) return ImageIcon;
  if (mime.startsWith("video/")) return Film;
  if (mime.startsWith("audio/")) return Music;
  if (mime.includes("zip") || mime.includes("7z") || mime.includes("compressed")) return FileArchive;
  if (mime.includes("sheet") || filename?.match(/\.(xls|xlsx|csv)$/i)) return FileSpreadsheet;
  if (mime.includes("presentation") || filename?.match(/\.(ppt|pptx)$/i)) return Presentation;
  return FileText;
}

function fmtKB(n) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} kB`;
  return `${(n / 1024 / 1024).toFixed(2)} MB`;
}

/**
 * Inline chip rendered inside a Pulse bubble or a Certify mail view.
 * Uses the axios `api` client (auto Authorization header) to fetch the
 * blob and trigger a browser download.
 *
 * Props:
 * - att: { attachment_id, filename, mime, size, sha3_512_hex }
 * - mine: bool (changes color for own bubble inversion)
 * - dark: bool (force light bg on yellow bubble)
 */
export function AttachmentChip({ att, mine = false, dark = false }) {
  const Icon = iconFor(att.mime, att.filename);
  const onDownload = async () => {
    try {
      const r = await api.get(`/attachments/${att.attachment_id}`, { responseType: "blob" });
      const url = window.URL.createObjectURL(new Blob([r.data], { type: att.mime }));
      const a = document.createElement("a");
      a.href = url;
      a.download = att.filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      console.error("Download error", e);
      alert(e?.response?.data?.detail || "Download fallito");
    }
  };

  // Determine theme classes
  const isYellowBubble = mine && !dark;
  const wrapperClasses = isYellowBubble
    ? "bg-[#0a1020]/15 border-[#0a1020]/30 text-[#0a1020]"
    : "bg-[rgba(212,175,55,0.08)] border-[var(--lattice-border-strong)] text-white";
  const subClasses = isYellowBubble ? "text-[#0a1020]/60" : "text-[var(--lattice-text-3)]";

  return (
    <button
      type="button"
      onClick={onDownload}
      data-testid={`attachment-chip-${att.attachment_id}`}
      className={`w-full max-w-[320px] border flex items-center gap-2 px-2.5 py-2 hover:opacity-90 transition-opacity text-left ${wrapperClasses}`}
      title={`SHA3-512: ${(att.sha3_512_hex || "").slice(0, 32)}…`}
    >
      <Icon size={20} className="shrink-0" />
      <div className="flex-1 min-w-0">
        <div className="font-mono-data text-[11px] truncate">{att.filename}</div>
        <div className={`font-mono-data text-[9px] uppercase tracking-wider ${subClasses}`}>
          {fmtKB(att.size)} · {(att.mime || "file").split("/")[1] || att.mime}
        </div>
      </div>
      <Download size={14} className="shrink-0 opacity-70" />
    </button>
  );
}
