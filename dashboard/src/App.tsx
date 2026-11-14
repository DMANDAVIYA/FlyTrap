import { useState } from "react";
import { Approvals } from "./components/Approvals";
import { Counters } from "./components/Counters";
import { LiveMap } from "./components/LiveMap";
import { LockdownOverlay } from "./components/Lockdown";
import { Loot } from "./components/Loot";
import { Replay } from "./components/Replay";
import { Report } from "./components/Report";
import { Roster } from "./components/Roster";
import { Sessions } from "./components/Sessions";
import { Stream } from "./components/Streams";
import { TopBar } from "./components/TopBar";
import { useFeed } from "./feed";

export default function App() {
  const s = useFeed();
  const [picked, setPicked] = useState<string | null>(null);
  const lockdown = s.lockdown.state !== "off";

  return (
    <div className={`h-screen min-h-[960px] p-3 flex flex-col gap-3 ${lockdown ? "outline outline-4 outline-warn/60 -outline-offset-4" : ""}`}>
      <LockdownOverlay lock={s.lockdown} />
      <TopBar s={s} />
      <Counters stats={s.stats} />
      <div className="grid grid-cols-12 gap-3 flex-[1.35] min-h-0">
        <LiveMap s={s} />
        <Sessions s={s} picked={picked} onPick={setPicked} />
      </div>
      <div className="grid grid-cols-12 gap-3 flex-1 min-h-0">
        <Stream title="Red swarm · raiders" items={s.red} color="var(--trap)" empty="Raiders are idle." />
        <Stream title="Blue swarm · defenders" items={s.blue} color="var(--real)" empty="Defenders are watching." />
        <Loot s={s} />
      </div>
      <div className="grid grid-cols-12 gap-3 flex-[1.1] min-h-0">
        <Report s={s} picked={picked} onPick={setPicked} />
        <Approvals s={s} />
        <div className="col-span-3 flex flex-col gap-3 min-h-0">
          <div className="flex-1 min-h-0 flex flex-col"><Roster s={s} /></div>
          <Replay s={s} />
        </div>
      </div>
    </div>
  );
}
