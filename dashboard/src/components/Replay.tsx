import { useEffect, useState } from "react";
import { goLive, listRuns, replay, type State } from "../feed";

export function Replay({ s }: { s: State }) {
  const [runs, setRuns] = useState<{ run: string; current: boolean }[]>([]);
  const [run, setRun] = useState("");
  const [speed, setSpeed] = useState(1);
  useEffect(() => {
    listRuns().then((d) => {
      const list = (d.runs ?? []).map((r: { run: string }) => ({ run: r.run, current: r.run === d.recording }));
      setRuns(list);
      setRun((cur) => cur || list.find((r: { current: boolean }) => !r.current)?.run || list[0]?.run || "");
    }).catch(() => {});
  }, [s.replay.active]);
  return (
    <section className="panel px-3 py-2 flex items-center gap-2">
      <h2 className="panel-title shrink-0">Replay</h2>
      <select value={run} onChange={(e) => setRun(e.target.value)}
        className="bg-bg border border-line rounded px-2 py-1 font-mono text-xs min-w-0 flex-1">
        {!runs.length && <option value="">no recorded runs yet</option>}
        {runs.map((r) => <option key={r.run} value={r.run}>{r.run}{r.current ? " (recording)" : ""}</option>)}
      </select>
      <div className="flex gap-1.5 shrink-0">
        {[1, 4].map((x) => (
          <button key={x} className={`btn !py-1 !px-2 ${speed === x ? "border-text2" : ""}`} onClick={() => setSpeed(x)}>{x}×</button>
        ))}
        {s.replay.active
          ? <button className="btn btn-ok !py-1 !px-2" onClick={() => goLive()}>Live</button>
          : <button className="btn btn-warn !py-1 !px-2" disabled={!run} onClick={() => replay(run, speed)}>Play</button>}
      </div>
    </section>
  );
}
