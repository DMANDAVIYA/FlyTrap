import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { control, type State } from "@/feed";
import type { SessionData } from "@/types";
import { short } from "../Panel";

/*
 * The raw view's command line. Every command does what a console button does, or reads the live
 * feed; nothing here is simulated. ":" or "/" focuses it, Up/Down walk the history, Tab completes.
 */

type Line = { kind: "in" | "out" | "err"; text: string };

const HELP: [string, string][] = [
  ["release", "release the swarm"],
  ["stop | kill", "kill switch: stop every raider, drone and the crowd"],
  ["reset", "reset Tartarus"],
  ["lockdown", "start a lockdown (10 s countdown)"],
  ["unlock", "end or cancel the lockdown"],
  ["approve <id> | reject <id>", "decide a Zeus card"],
  ["zeus", "list the Zeus cards"],
  ["stats", "the live readings"],
  ["sessions [text]", "trapped sessions, optionally filtered"],
  ["report <session|raider>", "open a session's incident report"],
  ["details", "open the details panel"],
  ["cards", "back to the card view"],
  ["clear", "clear this log"],
];
const COMMANDS = ["release", "stop", "kill", "reset", "lockdown", "unlock", "approve", "reject", "zeus", "stats", "sessions", "report", "details", "cards", "clear", "help"];

const typing = (t: EventTarget | null) =>
  t instanceof HTMLElement && (t.isContentEditable || ["INPUT", "TEXTAREA", "SELECT"].includes(t.tagName));

/** A session by full id, short id (s_ab12cd) or raider name (pandora-2); live ones first. */
function find(s: State, q: string): SessionData | undefined {
  const key = q.toLowerCase();
  const all = Object.values(s.sessions).sort((a, b) => Number(!!a.ended) - Number(!!b.ended));
  return all.find((x) => x.session === q) ?? all.find((x) => x.session.startsWith(q)) ?? all.find((x) => (x.raider ?? "").toLowerCase() === key);
}

export function CommandLine({ s, onReport, onDetails, onExit }: {
  s: State; onReport: (sid: string) => void; onDetails: () => void; onExit: () => void;
}) {
  const [log, setLog] = useState<Line[]>([{ kind: "out", text: "type help for commands · : or / jumps here" }]);
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const history = useRef<string[]>([]);
  const at = useRef(-1);
  const input = useRef<HTMLInputElement>(null);
  const out = useRef<HTMLDivElement>(null);

  useEffect(() => {
    input.current?.focus();
    const onKey = (e: globalThis.KeyboardEvent) => {
      if ((e.key === ":" || e.key === "/") && !typing(e.target) && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        input.current?.focus();
      }
    };
    addEventListener("keydown", onKey);
    return () => removeEventListener("keydown", onKey);
  }, []);
  useEffect(() => {
    out.current?.scrollTo({ top: out.current.scrollHeight });
  }, [log]);

  const print = (...lines: Line[]) => setLog((l) => [...l, ...lines].slice(-300));
  const say = (text: string) => print({ kind: "out", text });
  const fail = (text: string) => print({ kind: "err", text });

  const act = async (action: string) => {
    const res = await control(action);
    if (res.ok) say(`ok · ${res.state ?? res.approval?.status ?? action}`);
    else fail(res.error ?? `${action} failed`);
  };

  const run = async (raw: string) => {
    const [cmd = "", ...args] = raw.trim().split(/\s+/);
    switch (cmd.toLowerCase()) {
      case "":
        return;
      case "help":
        return print(...HELP.map(([c, d]) => ({ kind: "out" as const, text: `${c.padEnd(28)}${d}` })));
      case "release":
      case "reset":
      case "lockdown":
        return act(cmd.toLowerCase());
      case "stop":
      case "kill":
        return act("stop");
      case "unlock":
        return act("cancel_lockdown");
      case "approve":
      case "reject": {
        const id = Number(args[0]);
        if (!Number.isInteger(id)) return fail(`usage: ${cmd} <id> · see zeus for the ids`);
        return act(`${cmd.toLowerCase()}/${id}`);
      }
      case "zeus": {
        const cards = Object.values(s.approvals);
        if (!cards.length) return say("no Zeus cards");
        return print(...cards.map((a) => ({ kind: "out" as const, text: `#${a.id}  ${a.status.padEnd(9)} ${a.kind.padEnd(12)} ${a.summary}` })));
      }
      case "stats": {
        const t = s.stats;
        return say(`exposed ${t.real_records_exposed} · trapped ${t.trapped} · active ${t.active_sessions ?? "-"} · flip ${t.avg_flip_ms?.toFixed(2) ?? "-"} ms · `
          + `fake records ${t.fake_records_taken} · keys used ${t.canaries_fired} · requests ${t.requests_total ?? "-"}`);
      }
      case "sessions": {
        const q = args.join(" ").toLowerCase();
        const rows = Object.values(s.sessions).filter((x) => x.side !== "real")
          .filter((x) => !q || [x.session, x.raider, x.label, x.pod, x.stage, x.side].some((f) => String(f ?? "").toLowerCase().includes(q)));
        if (!rows.length) return say(q ? `no trapped session matches ${q}` : "no trapped sessions");
        return print(...rows.slice(0, 20).map((x) => ({
          kind: "out" as const,
          text: `${short(x.session).padEnd(10)}${(x.raider ?? "-").padEnd(14)}${x.label.padEnd(10)}${(x.side === "blocked" ? "blocked" : x.pod ?? "-").padEnd(9)}${x.ended ? "left" : x.stage}`,
        })), ...(rows.length > 20 ? [{ kind: "out" as const, text: `… ${rows.length - 20} more, narrow it with sessions <text>` }] : []));
      }
      case "report":
      case "open": {
        if (!args[0]) return fail("usage: report <session|raider>");
        const hit = find(s, args[0]);
        if (!hit) return fail(`no session matches ${args[0]}`);
        onReport(hit.session);
        return say(`opened the report for ${hit.raider ?? short(hit.session)}`);
      }
      case "details":
        onDetails();
        return say("opened the details panel");
      case "cards":
      case "exit":
        return onExit();
      case "clear":
        return setLog([]);
      default:
        return fail(`unknown command: ${cmd} · type help`);
    }
  };

  const submit = async () => {
    if (busy) return; // keep focus; a command still running ignores Enter
    const line = value;
    setValue("");
    at.current = -1;
    if (!line.trim()) return;
    history.current = [...history.current.filter((h) => h !== line), line].slice(-50);
    print({ kind: "in", text: line });
    setBusy(true);
    try {
      await run(line);
    } catch (err) {
      fail(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    const h = history.current;
    if (e.key === "Enter") {
      e.preventDefault();
      void submit();
    } else if (e.key === "ArrowUp" && h.length) {
      e.preventDefault();
      at.current = at.current < 0 ? h.length - 1 : Math.max(0, at.current - 1);
      setValue(h[at.current]);
    } else if (e.key === "ArrowDown" && at.current >= 0) {
      e.preventDefault();
      at.current = at.current + 1 >= h.length ? -1 : at.current + 1;
      setValue(at.current < 0 ? "" : h[at.current]);
    } else if (e.key === "Tab") {
      const word = value.trimStart();
      if (!word || word.includes(" ")) return;
      const hits = COMMANDS.filter((c) => c.startsWith(word.toLowerCase()));
      e.preventDefault();
      if (hits.length === 1) setValue(`${hits[0]} `);
      else if (hits.length > 1) say(hits.join("  "));
    } else if (e.key === "Escape") {
      input.current?.blur();
    }
  };

  // focus shows on the box border, the way a terminal pane lights up, not as a ring around the input
  return (
    <section aria-label="Command line" className="relative flex min-h-0 flex-col border border-line2 pt-2.5 focus-within:border-green/60">
      <h3 className="absolute -top-[0.7em] left-2 whitespace-nowrap bg-bg px-1 text-[11px] font-normal leading-none">
        <span className="text-text2">[ </span><span className="text-green">command</span><span className="text-text2"> · help · : to focus ]</span>
      </h3>
      <div ref={out} role="log" aria-live="polite" className="max-h-[7.5rem] min-h-[3rem] overflow-y-auto px-2 scroll-thin">
        {log.map((l, i) => (
          <div key={i} className={`whitespace-pre-wrap [overflow-wrap:anywhere] ${l.kind === "in" ? "text-text" : l.kind === "err" ? "text-warn" : "text-text2"}`}>
            {l.kind === "in" ? <><span className="text-green">dolos&gt; </span>{l.text}</> : l.text}
          </div>
        ))}
      </div>
      <label className="flex items-center gap-2 border-t border-line px-2 py-1.5">
        <span className="text-green" aria-hidden>dolos&gt;</span>
        <input
          ref={input}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={onKeyDown}
          aria-busy={busy}
          aria-label="Command"
          spellCheck={false}
          autoComplete="off"
          className="min-w-0 flex-1 bg-transparent text-text outline-none placeholder:text-text2/60 focus-visible:outline-none"
          placeholder="type a command, e.g. stats or report pandora"
        />
      </label>
    </section>
  );
}
