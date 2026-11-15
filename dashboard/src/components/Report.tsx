import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { State } from "../feed";
import { Panel, short } from "./Panel";

export function Report({ s, picked, onPick, className = "" }: { s: State; picked: string | null; onPick: (sid: string) => void; className?: string }) {
  const ids = Object.keys(s.reports);
  const current = picked && (ids.includes(picked) || s.sessions[picked]) ? picked : ids[ids.length - 1] ?? null;
  const [md, setMd] = useState<string | null>(null);

  useEffect(() => {
    if (!current) return setMd(null);
    const known = s.reports[current];
    if (known) return setMd(known);
    setMd(null);
    fetch(`/api/reports/${current}`).then((r) => (r.ok ? r.json() : null)).then((d) => d && setMd(d.markdown)).catch(() => {});
  }, [current, s.reports]);

  return (
    <Panel title="Incident report · Clio" className={className} bodyClass="overflow-y-auto scroll-thin"
      right={
        <div className="flex gap-1 items-center">
          {ids.slice(-5).map((id) => (
            <button key={id} onClick={() => onPick(id)}
              className={`font-mono text-xs px-1.5 py-0.5 rounded border ${id === current ? "border-text2" : "border-line text-text2"}`} title={id}>{s.sessions[id]?.raider ?? short(id)}</button>
          ))}
        </div>
      }>
      <div className="p-4 md">
        {md ? <ReactMarkdown remarkPlugins={[remarkGfm]}>{md}</ReactMarkdown>
          : <p className="text-text2 text-sm">{current ? `No report for ${current} yet.` : "Reports appear when a trapped session ends, or on demand."}</p>}
      </div>
    </Panel>
  );
}
