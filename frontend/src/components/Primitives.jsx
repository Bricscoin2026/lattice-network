export function PageHeader({ eyebrow, title, subtitle, right }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-6 pb-6 border-b hairline mb-6">
      <div className="max-w-3xl">
        <div className="eyebrow mb-3">{eyebrow}</div>
        <h1 className="font-display text-4xl sm:text-5xl text-white leading-[1.05]">{title}</h1>
        {subtitle ? (
          <p className="mt-3 text-[13px] sm:text-sm text-[var(--lattice-text-3)] leading-relaxed max-w-2xl">
            {subtitle}
          </p>
        ) : null}
      </div>
      {right ? <div className="flex items-center gap-3">{right}</div> : null}
    </div>
  );
}

export function StatPanel({ label, value, sub, testId, accent = false, icon: Icon }) {
  return (
    <div data-testid={testId} className="surface p-5 relative overflow-hidden">
      {accent ? <div className="absolute top-0 left-0 h-px w-12 bg-[var(--lattice-gold)]" /> : null}
      <div className="flex items-start justify-between">
        <div className="eyebrow">{label}</div>
        {Icon ? <Icon size={14} strokeWidth={1.5} className="text-[var(--lattice-gold)] opacity-80" /> : null}
      </div>
      <div className="mt-4 font-display text-3xl sm:text-4xl text-white leading-none">{value}</div>
      {sub ? <div className="mt-3 font-mono-data text-[11px] text-[var(--lattice-text-3)] tracking-wide">{sub}</div> : null}
    </div>
  );
}

export function SectionPanel({ eyebrow, title, subtitle, right, children, testId }) {
  return (
    <section data-testid={testId} className="surface">
      <header className="flex items-end justify-between px-5 py-4 border-b hairline gap-4 flex-wrap">
        <div>
          {eyebrow ? <div className="eyebrow mb-1">{eyebrow}</div> : null}
          <h2 className="font-display text-2xl text-white leading-none">{title}</h2>
          {subtitle ? <div className="mt-1 text-[12px] text-[var(--lattice-text-3)]">{subtitle}</div> : null}
        </div>
        {right ? <div className="flex items-center gap-2">{right}</div> : null}
      </header>
      <div>{children}</div>
    </section>
  );
}

export function HashCell({ value, color = "default" }) {
  if (!value) return <span className="text-[var(--lattice-text-4)]">—</span>;
  const cls = color === "gold" ? "hash-gold" : "hash-mono";
  const short = `${value.slice(0, 10)}…${value.slice(-10)}`;
  return (
    <span title={value} className={cls}>
      {short}
    </span>
  );
}

export function EmptyRow({ colSpan, text }) {
  return (
    <tr>
      <td colSpan={colSpan} className="text-center py-10 text-[var(--lattice-text-4)] font-mono-data text-[11px] tracking-[0.18em] uppercase">
        {text}
      </td>
    </tr>
  );
}
