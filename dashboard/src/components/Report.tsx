import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { State } from "../feed";
import { Panel, short } from "./Panel";

async function fetchReport(sid: string): Promise<string | null> {
  try {
    const r = await fetch(`/api/reports/${sid}`);
    return r.ok ? ((await r.json())?.markdown ?? null) : null;
  } catch {
    return null;
  }
}

export function Report({ s, picked, onPick, className = "" }: { s: State; picked: string | null; onPick: (sid: string) => void; className?: string }) {
  const ids = Object.keys(s.reports);
  const latest = ids[ids.length - 1] ?? null;
  const current = picked ?? latest;
  const name = (sid: string) => s.sessions[sid]?.raider ?? short(sid);
  const [view, setView] = useState<{ md: string | null; note: string | null; loading: boolean }>({ md: null, note: null, loading: false });

  // Show the picked session's report; if Clio has not written it yet, say so and fall back to the latest one.
  useEffect(() => {
    if (!current) return setView({ md: null, note: null, loading: false });
    let off = false;
    setView((v) => ({ ...v, loading: true }));
    (async () => {
      const md = s.reports[current] ?? (await fetchReport(current));
      if (off) return;
      if (md) return setView({ md, note: null, loading: false });
      const fallback = latest && latest !== current ? s.reports[latest] ?? (await fetchReport(latest)) : null;
      if (off) return;
      setView({
        md: fallback,
        note: `Clio writes ${name(current)}'s report when its session ends.${fallback && latest ? ` Showing the latest one: ${name(latest)}.` : ""}`,
        loading: false,
      });
    })();
    return () => { off = true; };
    // name() reads sessions only for labels; the report follows the picked id and the report set.
  }, [current, latest, s.reports]);

  return (
    <Panel title="Incident report · Clio" className={className} bodyClass="overflow-y-auto scroll-thin">
      {ids.length > 0 && (
        <div className="flex flex-wrap gap-1.5 border-b border-line px-4 py-2.5">
          {ids.slice(-6).map((id) => (
            <button key={id} onClick={() => onPick(id)} title={id}
              className={`rounded-full border px-2.5 py-0.5 text-xs capitalize ${id === current ? "border-green/60 text-green" : "border-line2 text-text2 hover:text-text"}`}>
              {name(id)}
            </button>
          ))}
        </div>
      )}
      <div className="md p-4">
        {view.note && <p className="!mt-0 mb-4 rounded-lg border border-line2 px-3 py-2 text-sm !text-text2">{view.note}</p>}
        {view.md ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{view.md}</ReactMarkdown>
          : !view.note && (
            <p className="text-sm !text-text2">
              {view.loading ? "Loading the report…" : "Reports appear here when a trapped session ends."}
            </p>
          )}
      </div>
    </Panel>
  );
}
