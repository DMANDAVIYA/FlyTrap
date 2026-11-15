import { useMemo, useState, type ReactNode } from "react";
import { GlowCard } from "@/components/ui/glow-card";
import type { State } from "@/feed";
import { agentColor, clock, short } from "../Panel";

const TABS = ["Trapped", "Messages", "Requests", "Trackers"] as const;
type Tab = (typeof TABS)[number];

const LABEL: Record<string, { text: string; cls: string }> = {
  ai_agent: { text: "AI agent", cls: "bg-green/15 text-green" },
  scanner: { text: "Scanner", cls: "bg-real/15 text-real" },
  human: { text: "Human", cls: "bg-text/[.07] text-text2" },
  unknown: { text: "Unlabelled", cls: "bg-text/[.05] text-text2" },
};
const SIDE: Record<string, { text: string; cls: string }> = {
  trap: { text: "Tartarus", cls: "bg-green/15 text-green" },
  real: { text: "Olympus", cls: "bg-real/15 text-real" },
  blocked: { text: "Blocked", cls: "bg-text/[.07] text-text2" },
};

const Pill = ({ cls, children }: { cls: string; children: ReactNode }) => (
  <span className={`inline-flex whitespace-nowrap rounded-full px-2.5 py-1 text-[11.5px] font-semibold ${cls}`}>{children}</span>
);
const Th = ({ children, className = "" }: { children: ReactNode; className?: string }) => (
  <th className={`sticky top-0 z-10 whitespace-nowrap bg-[#171717] px-3 pb-2 pt-1 text-[12px] font-semibold text-text2 ${className}`}>{children}</th>
);
const Empty = ({ cols, children }: { cols: number; children: ReactNode }) => (
  <tr><td colSpan={cols} className="px-3 py-6 text-center text-text2">{children}</td></tr>
);

/** The working table: trapped visitors (default; a row opens its report), agent messages, raw requests and tracked keys. */
export function Activity({ s, picked, onOpen, className = "" }: {
  s: State; picked: string | null; onOpen: (sid: string) => void; className?: string;
}) {
  const [tab, setTab] = useState<Tab>("Trapped");
  const trapped = useMemo(() => Object.values(s.sessions).filter((x) => x.side !== "real")
    .sort((a, b) => Number(!!a.ended) - Number(!!b.ended) || (b.last_seen ?? "").localeCompare(a.last_seen ?? "")), [s.sessions]);
  const messages = useMemo(() => [...s.red.slice(-60), ...s.blue.slice(-60)].sort((a, b) => b.t - a.t).slice(0, 60), [s.red, s.blue]);
  const requests = useMemo(() => s.events.slice(-60).reverse(), [s.events]);
  const who = (sid: string) => s.sessions[sid]?.raider ?? short(sid);
  const count: Record<Tab, number> = {
    Trapped: trapped.length, Messages: s.red.length + s.blue.length, Requests: s.events.length, Trackers: s.canaries.length + s.campaigns.length,
  };

  return (
    <GlowCard label="Activity" className={className}>
      <div role="tablist" aria-label="Activity" className="-mx-1 mb-3 flex gap-1 overflow-x-auto pb-1 scroll-thin">
        {TABS.map((t) => (
          <button key={t} role="tab" aria-selected={t === tab} onClick={() => setTab(t)}
            className={`shrink-0 rounded-full px-3 py-1.5 text-[14px] transition-colors ${t === tab ? "bg-text/[.07] font-semibold text-text" : "text-text2 hover:text-text"}`}>
            {t}<span className="ml-1.5 font-mono text-[11px] tabular text-text2">{count[t]}</span>
          </button>
        ))}
      </div>

      <div role="tabpanel" aria-label={tab} className="-mx-2 min-h-0 flex-1 overflow-auto px-2 scroll-thin">
        <table className="w-full text-left text-[13px]">
          {tab === "Trapped" && (
            <>
              <thead className="text-text"><tr className="[&>th]:border-b [&>th]:border-dashed [&>th]:border-line2"><Th>Last seen</Th><Th>Visitor</Th><Th>Where</Th><Th className="text-right">Label</Th></tr></thead>
              <tbody>
                {trapped.slice(0, 80).map((x) => (
                  <tr key={x.session} onClick={() => onOpen(x.session)} title="Open the incident report"
                    className={`cursor-pointer transition-colors hover:bg-text/[.04] ${picked === x.session ? "bg-text/[.06]" : ""} ${x.ended ? "opacity-55" : ""}`}>
                    <td className="whitespace-nowrap px-3 py-1.5 font-mono tabular text-text2">{x.last_seen ? clock(x.last_seen) : "—"}</td>
                    <td className="px-3 py-1.5">
                      <button className="block text-left font-semibold capitalize text-text" aria-label={`Open the report for ${x.raider ?? "this visitor"}`} onClick={(e) => { e.stopPropagation(); onOpen(x.session); }}>
                        {x.raider ?? "Unknown visitor"}
                      </button>
                      <span className="font-mono text-[11.5px] text-text2">{short(x.session)}</span>
                    </td>
                    <td className="whitespace-nowrap px-3 py-1.5 text-text2">{x.side === "blocked" ? "blocked" : x.pod ?? "tartarus"}{x.ended ? " · left" : ` · ${x.stage}`}</td>
                    <td className="px-3 py-1.5 text-right"><Pill cls={(LABEL[x.label] ?? LABEL.unknown).cls}>{(LABEL[x.label] ?? LABEL.unknown).text}</Pill></td>
                  </tr>
                ))}
                {!trapped.length && <Empty cols={4}>{s.stats.trapped ? "No trapped visitor is active right now." : "No one trapped yet. Press Release the swarm to start the raiders."}</Empty>}
              </tbody>
            </>
          )}
          {tab === "Messages" && (
            <>
              <thead><tr className="[&>th]:border-b [&>th]:border-dashed [&>th]:border-line2"><Th>Time</Th><Th>Agent</Th><Th>Session</Th><Th>Message</Th></tr></thead>
              <tbody>
                {messages.map((m, i) => (
                  <tr key={`${m.t}-${i}`} className={m.kind === "alert" ? "bg-warn/[.06]" : ""}>
                    <td className="whitespace-nowrap px-3 py-2 align-top font-mono tabular text-text2">{clock(m.t)}</td>
                    <td className="px-3 py-2 align-top font-semibold uppercase" style={{ color: agentColor(m.agent) }}>{m.agent}</td>
                    <td className="px-3 py-2 align-top font-mono text-text2">{m.session && m.session !== "-" ? short(m.session) : "—"}</td>
                    <td className={`px-3 py-2 leading-snug [overflow-wrap:anywhere] ${m.kind === "alert" ? "text-warn" : "text-text/90"}`}>{m.text}</td>
                  </tr>
                ))}
                {!messages.length && <Empty cols={4}>Hermes carries every agent's message here once the swarm is released.</Empty>}
              </tbody>
            </>
          )}
          {tab === "Requests" && (
            <>
              <thead><tr className="[&>th]:border-b [&>th]:border-dashed [&>th]:border-line2"><Th>Time</Th><Th>Request</Th><Th>Status</Th><Th>Tripwire</Th><Th className="text-right">Side</Th></tr></thead>
              <tbody>
                {requests.map((e, i) => (
                  <tr key={`${e.id}-${i}`}>
                    <td className="whitespace-nowrap px-3 py-2 font-mono tabular text-text2">{clock(e.ts)}</td>
                    <td className="max-w-[16rem] truncate px-3 py-2 font-mono" title={`${e.method ?? ""} ${e.path ?? ""}`}>{e.method} {e.path ?? e.kind}</td>
                    <td className="px-3 py-2 font-mono tabular text-text2">{e.status ?? "—"}</td>
                    <td className="px-3 py-2 font-mono text-green">{e.tripwire ?? ""}</td>
                    <td className="px-3 py-2 text-right">{e.side && SIDE[e.side] ? <Pill cls={SIDE[e.side].cls}>{SIDE[e.side].text}</Pill> : <span className="text-text2">{e.kind}</span>}</td>
                  </tr>
                ))}
                {!requests.length && <Empty cols={5}>Requests stream in here as they pass Charon.</Empty>}
              </tbody>
            </>
          )}
          {tab === "Trackers" && (
            <>
              <thead><tr className="[&>th]:border-b [&>th]:border-dashed [&>th]:border-line2"><Th>Key</Th><Th>Shown to</Th><Th>Used by</Th><Th className="text-right">Link</Th></tr></thead>
              <tbody>
                {s.canaries.slice().reverse().map((c, i) => (
                  <tr key={`${c.event_id}-${i}`}>
                    <td className="px-3 py-2.5 font-mono text-green">{c.kind.replace("_", " ")}</td>
                    <td className="px-3 py-2.5 capitalize">{who(c.planted_in)}</td>
                    <td className="px-3 py-2.5 capitalize">{who(c.used_by)}</td>
                    <td className="px-3 py-2.5 text-right">{c.planted_in !== c.used_by ? <Pill cls="bg-green/15 text-green">Shared key</Pill> : <span className="font-mono text-text2">#{c.event_id}</span>}</td>
                  </tr>
                ))}
                {s.campaigns.map((c) => (
                  <tr key={`c${c.id}`}>
                    <td className="px-3 py-2.5 font-semibold text-green">{c.name}</td>
                    <td colSpan={2} className="px-3 py-2.5 capitalize">{c.sessions.map(who).join(" + ")}</td>
                    <td className="px-3 py-2.5 text-right"><Pill cls="bg-text/[.08] text-text">Campaign</Pill></td>
                  </tr>
                ))}
                {!s.canaries.length && !s.campaigns.length && <Empty cols={4}>Every key shown in Tartarus is unique to one visitor. When one is used, it names the visitor here.</Empty>}
              </tbody>
            </>
          )}
        </table>
      </div>

    </GlowCard>
  );
}
