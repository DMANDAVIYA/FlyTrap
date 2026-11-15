import { useState, type ReactNode, type Ref } from "react";
import { control, type State } from "@/feed";
import { BLUE, RED, ROLE, type SessionData, type StreamItem } from "@/types";
import { clock, short } from "../Panel";
import { useStick } from "../Streams";

/*
 * Raw view: every field of the live feed as a terminal UI, attackers left and defenders right.
 * Only feed data is printed. Bars and sparklines are drawn with elements, because the bundled
 * JetBrains Mono subsets carry no block characters.
 */

const sideTone = (side?: string | null) => (side === "real" ? "text-real" : side === "blocked" ? "text-text2" : "text-green");
const num = (n: number | null | undefined, d = 2) => (n == null ? "-" : n.toFixed(d));
const TAG: Record<StreamItem["kind"], string> = { thought: "think", action: "act", note: "note", alert: "ALERT" };

function Box({ title, meta, tone = "text-text", className = "", bodyRef, children }: {
  title: string; meta?: ReactNode; tone?: string; className?: string; bodyRef?: Ref<HTMLDivElement>; children: ReactNode;
}) {
  return (
    <section aria-label={title} className={`relative flex min-h-0 flex-col border border-line2 pt-2.5 ${className}`}>
      <h3 className="absolute -top-[0.7em] left-2 whitespace-nowrap bg-bg px-1 text-[11px] font-normal leading-none">
        <span className="text-text2">[ </span><span className={tone}>{title}</span>
        {meta != null && <span className="text-text2"> · {meta}</span>}
        <span className="text-text2"> ]</span>
      </h3>
      <div ref={bodyRef} className="min-h-0 flex-1 overflow-auto px-2 pb-1.5 scroll-thin">{children}</div>
    </section>
  );
}

function Spark({ values, max }: { values: number[]; max: number }) {
  return (
    <span aria-hidden className="inline-flex h-[1.05em] items-end gap-px align-[-0.2em]">
      {values.map((v, i) => (
        <span key={i} className="w-[0.45ch] bg-current" style={{ height: `${Math.max(6, (v / max) * 100)}%` }} />
      ))}
    </span>
  );
}

function Meter({ value, total, tone }: { value: number; total: number; tone: string }) {
  return (
    <span aria-hidden className="relative inline-block h-[0.75em] w-[16ch] bg-line/70 align-[-0.05em]">
      <span className={`absolute inset-y-0 left-0 bg-current ${tone}`} style={{ width: `${total ? (value / total) * 100 : 0}%` }} />
    </span>
  );
}

function Log({ title, meta, tone, items, empty, className }: {
  title: string; meta: string; tone: string; items: StreamItem[]; empty: string; className?: string;
}) {
  const ref = useStick(items.length);
  return (
    <Box title={title} meta={meta} tone={tone} className={className} bodyRef={ref}>
      {items.length ? items.map((it, i) => {
        const muted = it.kind === "action" && it.status === "rejected";
        return (
          <div key={i} className={`[overflow-wrap:anywhere] ${it.kind === "alert" ? "text-warn" : ""}`}>
            <span className="text-text2">{clock(it.t)} </span>
            <span className={tone}>{it.agent.toUpperCase()}</span>
            {it.session && it.session !== "-" && <span className="text-text2"> [{short(it.session)}]</span>}
            <span className="text-text2"> {TAG[it.kind]}{it.kind === "action" ? `:${it.status}` : ""} </span>
            <span className={muted ? "text-text2 line-through" : it.kind === "alert" ? "" : "text-text"}>{it.text}</span>
          </div>
        );
      }) : <p className="text-text2">{empty}</p>}
    </Box>
  );
}

function Trapped({ s, picked, onPick, className }: { s: State; picked: string | null; onPick: (sid: string) => void; className?: string }) {
  const all = Object.values(s.sessions);
  const rows: SessionData[] = all.filter((x) => x.side !== "real")
    .sort((a, b) => Number(!!a.ended) - Number(!!b.ended) || Number(!!b.raider) - Number(!!a.raider) || (b.last_seen ?? "").localeCompare(a.last_seen ?? ""));
  const olympus = all.filter((x) => !x.ended && x.side === "real").length;
  return (
    <Box title="sessions" meta={`${rows.filter((x) => !x.ended).length} in tartarus · ${olympus} on olympus`} tone="text-green" className={className}>
      {rows.length ? (
        <table className="w-full whitespace-nowrap text-left">
          <thead className="text-text2">
            <tr>{["sid", "who", "label", "conf", "where", "stage", "risk", "ladder", "seen"].map((h) => <th key={h} className="pr-3 font-normal">{h}</th>)}</tr>
          </thead>
          <tbody>
            {rows.map((x) => (
              <tr key={x.session} className={`${picked === x.session ? "bg-green/10" : ""} ${x.ended ? "opacity-55" : ""}`}>
                <td className="pr-3">
                  <button className="text-text underline-offset-2 hover:underline" title={`${x.session}: open the incident report`} onClick={() => onPick(x.session)}>{short(x.session)}</button>
                </td>
                <td className="pr-3 text-green">{x.raider ?? "-"}</td>
                <td className="pr-3">{x.label}</td>
                <td className="pr-3 tabular">{x.confidence != null ? x.confidence.toFixed(2) : "-"}</td>
                <td className={`pr-3 ${sideTone(x.side)}`}>{x.side === "blocked" ? "blocked" : x.pod ?? "tartarus"}</td>
                <td className="pr-3">{x.ended ? "left" : x.stage}</td>
                <td className="pr-3 tabular">{x.risk}</td>
                <td className="pr-3">{x.ladder}{x.pace ? `/${x.pace}` : ""}</td>
                <td className="pr-3 text-text2">{x.last_seen ? clock(x.last_seen) : "-"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : <p className="text-text2">no trapped sessions yet · release the swarm to start the raiders</p>}
    </Box>
  );
}

function Requests({ s, className }: { s: State; className?: string }) {
  const tail = s.events.slice(-60);
  const ref = useStick(s.events.length ? s.events[s.events.length - 1].id : 0);
  return (
    <Box title="requests" meta={`last ${tail.length} of ${s.events.length}`} tone="text-green" className={className} bodyRef={ref}>
      {tail.length ? tail.map((e, i) => (
        <div key={`${e.id}-${i}`} className="whitespace-nowrap">
          <span className="text-text2">{clock(e.ts)} #{e.id} </span>
          <span className={`inline-block w-[8ch] ${sideTone(e.side)}`}>{e.side ?? e.kind}</span>
          <span>{e.method ?? ""} {e.path ?? ""} </span>
          {e.status != null && <span className={e.status >= 400 ? "text-text2" : "text-text"}>{e.status} </span>}
          {e.pod && <span className="text-text2">{e.pod} </span>}
          {e.tripwire && <span className="text-green">trip:{e.tripwire} </span>}
          {e.raider && <span className="text-green">{e.raider} </span>}
          {e.records ? <span className="text-text2">rec:{e.records} </span> : null}
          {e.gw_ms != null && <span className="text-text2">{e.gw_ms.toFixed(2)}ms</span>}
        </div>
      )) : <p className="text-text2">no requests yet</p>}
    </Box>
  );
}

function Zeus({ s }: { s: State }) {
  const [busy, setBusy] = useState<number | null>(null);
  const list = Object.values(s.approvals).sort((a, b) => Number(a.status !== "pending") - Number(b.status !== "pending") || b.id - a.id);
  const pending = list.filter((a) => a.status === "pending").length;
  const decide = async (id: number, action: "approve" | "reject") => {
    setBusy(id);
    try { await control(`${action}/${id}`); } finally { setBusy(null); }
  };
  return (
    <Box title="zeus" meta={pending ? `${pending} waiting` : "none waiting"} tone="text-warn" className={pending ? "max-h-[9.5rem] border-warn/70" : ""}>
      {list.length ? list.slice(0, 8).map((a) => (
        <div key={a.id} className={a.status === "pending" ? "text-warn" : "text-text2"}>
          #{a.id} {a.kind} <span className="text-text2">{a.status}</span> {a.summary}
          {a.status === "pending" && (
            <span className="ml-2 whitespace-nowrap">
              <button className="text-green hover:underline disabled:opacity-50" disabled={busy === a.id} onClick={() => decide(a.id, "approve")}>[approve]</button>{" "}
              <button className="text-text hover:underline disabled:opacity-50" disabled={busy === a.id} onClick={() => decide(a.id, "reject")}>[reject]</button>
            </span>
          )}
        </div>
      )) : <p className="text-text2">big moves wait here for a human</p>}
    </Box>
  );
}

function Roster({ title, names, idle, tone, s }: { title: string; names: readonly string[]; idle: string; tone: string; s: State }) {
  return (
    <Box title={title} meta={`${names.length}`} tone={tone}>
      <table className="w-full whitespace-nowrap text-left">
        <tbody>
          {names.map((n) => {
            const r = s.roster[n];
            const st = r?.state ?? idle;
            return (
              <tr key={n} className={st === "offline" ? "text-text2" : ""}>
                <td className={`pr-3 ${tone}`}>{n}</td>
                <td className="pr-3 text-text2">{ROLE[n]}</td>
                <td className={`pr-3 ${st === "acting" || st === "attacking" ? "text-text" : "text-text2"}`}>{st}{r?.mode === "rules" ? "·rules" : ""}</td>
                <td className="text-text2">{r?.session ? short(r.session) : ""}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </Box>
  );
}

export function RawConsole({ s, picked, onPick }: { s: State; picked: string | null; onPick: (sid: string) => void }) {
  const st = s.stats;
  const series = s.rps.slice(-40);
  const max = Math.max(1, ...series.map((d) => Math.max(d.real, d.trap)));
  const now = s.rps[s.rps.length - 1] ?? { real: 0, trap: 0 };
  const labels = st.sessions_by_label ?? {};
  const labelled = Object.values(labels).reduce((a, b) => a + b, 0);
  const raiderOf = (sid: string) => s.sessions[sid]?.raider ?? short(sid);
  const exposed = st.real_records_exposed;

  const head = (title: string, tone: string, sub: string, summary: string) => (
    <div className="flex items-baseline gap-3 whitespace-nowrap">
      <h2 className={`text-[13px] font-semibold ${tone}`}>{title}</h2>
      <span className="truncate text-text2">{sub}</span>
      <span aria-hidden className="h-px min-w-6 flex-1 self-center bg-line2" />
      <span className="text-text2">{summary}</span>
    </div>
  );

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3 font-mono text-[12px] leading-[1.45]">
      <div className="grid min-h-0 flex-1 gap-6 lg:grid-cols-2 lg:grid-rows-1 lg:gap-5">
        <section aria-label="Attackers" className="flex min-h-0 flex-col gap-4">
          {head("ATTACKERS", "text-green", "tartarus · raiders and trapped visitors",
            `${RED.filter((n) => s.roster[n]?.state === "attacking").length}/${RED.length} raiding`)}
          <div className="grid min-h-0 flex-1 gap-4 lg:grid-rows-[auto_minmax(0,1.3fr)_auto_minmax(0,1fr)_minmax(0,1fr)]">
            <Box title="traffic" meta="req/s, 2 s readings" tone="text-green">
              <div className="whitespace-nowrap"><span className="text-text2">trapped </span><span className="inline-block w-[7ch] text-right tabular text-green">{now.trap.toFixed(1)}</span> <span className="text-green"><Spark values={series.map((d) => d.trap)} max={max} /></span></div>
              <div className="whitespace-nowrap"><span className="text-text2">real    </span><span className="inline-block w-[7ch] text-right tabular text-real">{now.real.toFixed(1)}</span> <span className="text-real"><Spark values={series.map((d) => d.real)} max={max} /></span></div>
              <div className="truncate text-text2">
                gateway p50 <span className="text-text">{num(st.p50_gw_ms)}</span> p95 <span className="text-text">{num(st.p95_gw_ms)}</span> ms · requests <span className="text-text">{st.requests_total ?? "-"}</span> · flips <span className="text-text">{s.flips}</span>
                {s.lastFlip && <> · last <span className="text-green">{s.lastFlip.raider ?? short(s.lastFlip.session)}</span> → {s.lastFlip.pod} ({s.lastFlip.tripwire}, {Number(s.lastFlip.gw_ms).toFixed(2)} ms)</>}
              </div>
            </Box>
            <Trapped s={s} picked={picked} onPick={onPick} className="h-[260px] lg:h-auto" />
            <div className="grid gap-4 sm:grid-cols-2">
              <Roster title="raiders" names={RED} idle="idle" tone="text-green" s={s} />
              <Box title="loot" meta={`${st.fake_records_taken} fake records`} tone="text-green">
                <div className="text-text2">marked keys used <span className="text-text">{st.canaries_fired}</span> · campaigns <span className="text-text">{s.campaigns.length}</span></div>
                {Object.entries(st.tripwire_counts ?? {}).length > 0 && (
                  <div className="truncate text-text2">tripwires {Object.entries(st.tripwire_counts ?? {}).map(([k, v]) => `${k}:${v}`).join(" ")}</div>
                )}
                {s.canaries.slice(-4).reverse().map((c, i) => (
                  <div key={`${c.event_id}-${i}`} className="truncate">
                    <span className="text-green">{c.kind}</span> {raiderOf(c.planted_in)} → {raiderOf(c.used_by)}
                    {c.planted_in !== c.used_by && <span className="text-text2"> cross-session</span>}<span className="text-text2"> #{c.event_id}</span>
                  </div>
                ))}
                {s.campaigns.map((c) => (
                  <div key={c.id} className="truncate"><span className="text-green">{c.name}</span> {c.sessions.map(raiderOf).join(" + ")} <span className="text-text2">{c.reason}</span></div>
                ))}
              </Box>
            </div>
            <Log title="red swarm" meta={`${s.red.length} lines`} tone="text-green" items={s.red} empty="raiders are idle" className="h-[220px] lg:h-auto" />
            <Requests s={s} className="h-[220px] lg:h-auto" />
          </div>
        </section>

        <section aria-label="Defenders" className="flex min-h-0 flex-col gap-4 lg:border-l lg:border-line lg:pl-5">
          {head("DEFENDERS", "text-real", "olympus · the pantheon",
            `${BLUE.filter((n) => s.roster[n]?.state === "acting").length}/${BLUE.length} acting`)}
          <div className="grid min-h-0 flex-1 gap-4 lg:grid-rows-[auto_auto_auto_minmax(0,1fr)]">
            <Box title="vitals" tone="text-real" className={exposed ? "border-breach/70" : ""}>
              <div className="grid grid-cols-[auto_1fr] gap-x-4 sm:grid-cols-[auto_1fr_auto_1fr]">
                <span className="text-text2">real records exposed</span><span className={exposed ? "font-semibold text-breach" : "text-green"}>{exposed}</span>
                <span className="text-text2">trapped</span><span className="text-green">{st.trapped}</span>
                <span className="text-text2">active sessions</span><span>{st.active_sessions ?? "-"}</span>
                <span className="text-text2">flip avg</span><span>{num(st.avg_flip_ms)} ms</span>
                <span className="text-text2">canaries fired</span><span>{st.canaries_fired}</span>
                <span className="text-text2">real own records</span><span>{st.real_own_records ?? "-"}</span>
                <span className="text-text2">lockdown</span>
                <span className={s.lockdown.state === "off" ? "" : "text-warn"}>{s.lockdown.state}{s.lockdown.reason ? ` · ${s.lockdown.reason}` : ""}{s.lockdown.by ? ` · by ${s.lockdown.by}` : ""}</span>
                <span className="text-text2">reports</span><span>{Object.keys(s.reports).length}</span>
              </div>
            </Box>
            <Zeus s={s} />
            <div className="grid gap-4 sm:grid-cols-2">
              <Roster title="pantheon" names={BLUE} idle="watching" tone="text-real" s={s} />
              <Box title="argus labels" meta={`${labelled} labelled`} tone="text-real">
                {(["ai_agent", "scanner", "human", "unknown"] as const).map((k) => (
                  <div key={k} className="whitespace-nowrap">
                    <span className="inline-block w-[9ch] text-text2">{k.replace("_", " ")}</span>
                    <Meter value={labels[k] ?? 0} total={labelled} tone={k === "ai_agent" ? "text-green" : k === "scanner" ? "text-real" : "text-text2"} />
                    <span className="ml-2 tabular">{labels[k] ?? 0}</span>
                  </div>
                ))}
              </Box>
            </div>
            <Log title="blue swarm" meta={`${s.blue.length} lines`} tone="text-real" items={s.blue} empty="defenders are watching" className="h-[300px] lg:h-auto" />
          </div>
        </section>
      </div>

      <footer className="flex flex-wrap gap-x-4 border-t border-line pt-2 text-text2">
        <span className={s.connected ? "text-green" : ""}>ws {s.connected ? "live" : "offline"}</span>
        <span>mode {s.mode || "-"}</span>
        <span>replay {s.replay.active ? s.replay.run ?? "on" : "off"}</span>
        <span>events {s.events.length}</span>
        <span>sessions {Object.keys(s.sessions).length}</span>
        <span>red {s.red.length} · blue {s.blue.length}</span>
      </footer>
    </div>
  );
}
