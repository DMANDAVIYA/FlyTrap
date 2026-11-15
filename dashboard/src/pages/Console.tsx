import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Approvals } from "@/components/Approvals";
import { AgentLog } from "@/components/console/AgentLog";
import { Pantheon } from "@/components/console/Pantheon";
import { Taken } from "@/components/console/Taken";
import { Traffic } from "@/components/console/Traffic";
import { Visitors } from "@/components/console/Visitors";
import { Vitals } from "@/components/console/Vitals";
import { Drawer, type Tab } from "@/components/Drawer";
import { FlipToast } from "@/components/FlipToast";
import { LockdownOverlay } from "@/components/Lockdown";
import { Sessions } from "@/components/Sessions";
import { TopBar } from "@/components/TopBar";
import { useFeed } from "@/feed";
import { BLUE, RED } from "@/types";

// Two sides, mirrored: the attackers' lists sit on the left edge, the defenders' log on the right edge.
// Fixed to the viewport on laptops; stacked with normal scrolling below lg.
const ATTACK = "lg:grid-cols-2 lg:grid-rows-[minmax(0,.9fr)_minmax(0,1fr)_minmax(0,1fr)] " +
  "lg:[grid-template-areas:'traffic_traffic''trapped_raiders''trapped_taken']";
const DEFEND = "lg:grid-cols-2 lg:grid-rows-[minmax(0,.9fr)_minmax(0,1fr)_minmax(0,1fr)] " +
  "lg:[grid-template-areas:'vitals_vitals''pantheon_defenders''visitors_defenders']";

function Side({ id, title, sub, tone, summary, className = "", children }: {
  id: string; title: string; sub: string; tone: string; summary: string; className?: string; children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className={`flex min-h-0 flex-col gap-3 ${className}`}>
      <header className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <h2 id={id} className={`font-display text-[clamp(1.9rem,2.4vw,2.5rem)] font-[300] uppercase leading-none tracking-[0.04em] ${tone}`}>{title}</h2>
        <p className="text-xs text-text2">{sub}</p>
        <p className="ml-auto font-mono text-xs tabular text-text2">{summary}</p>
      </header>
      {children}
    </section>
  );
}

export default function Console() {
  const s = useFeed();
  const [picked, setPicked] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("Agents");
  const lockdown = s.lockdown.state !== "off";

  useEffect(() => {
    document.title = "Dolos · console";
  }, []);

  const close = useCallback(() => setOpen(false), []);
  const openTab = (t: Tab) => {
    setTab(t);
    setOpen(true);
  };
  const openReport = (sid: string) => {
    setPicked(sid);
    openTab("Report");
  };

  const raiding = RED.filter((n) => s.roster[n]?.state === "attacking").length;
  const inTartarus = Object.values(s.sessions).filter((x) => !x.ended && x.side !== "real").length;
  const acting = BLUE.filter((n) => s.roster[n]?.state === "acting").length;
  const exposed = s.stats.real_records_exposed;

  return (
    <div className={`flex min-h-[100svh] flex-col bg-bg lg:h-[100svh] ${lockdown ? "outline outline-4 -outline-offset-4 outline-warn/60" : ""}`}>
      <h1 className="sr-only">Dolos console</h1>
      <LockdownOverlay lock={s.lockdown} />
      <TopBar s={s} drawerOpen={open} onToggleDrawer={() => setOpen((o) => !o)} />
      <FlipToast s={s} />
      {/* overflow-x-clip: the drawer slides in from the right edge without widening the page. */}
      <main className="relative flex min-h-0 flex-1 flex-col overflow-x-clip p-4 sm:p-5">
        <div className="grid min-h-0 flex-1 gap-8 lg:grid-cols-2 lg:grid-rows-1 lg:gap-0">
          <Side id="side-attackers" title="Attackers" sub="Raiders and visitors trapped in Tartarus" tone="text-green"
            summary={`${raiding}/${RED.length} raiders active · ${inTartarus} in Tartarus now`} className="lg:pr-5">
            <div className={`grid min-h-0 flex-1 grid-cols-1 gap-4 md:grid-cols-2 ${ATTACK}`}>
              <Traffic rps={s.rps} stats={s.stats} className="min-h-[300px] md:col-span-2 lg:col-span-1 lg:min-h-0 lg:[grid-area:traffic]" />
              <Sessions s={s} picked={picked} onPick={openReport} className="min-h-[320px] lg:min-h-0 lg:[grid-area:trapped]" />
              <AgentLog title="Raider messages" items={s.red} empty="Raiders think out loud here once the swarm is released."
                onOpen={() => openTab("Agents")} className="h-[360px] lg:h-auto lg:min-h-0 lg:[grid-area:raiders]" />
              <Taken s={s} className="md:col-span-2 lg:col-span-1 lg:[grid-area:taken]" />
            </div>
          </Side>
          <Side id="side-defenders" title="Defenders" sub="The pantheon guarding Olympus" tone="text-real"
            summary={`${acting}/${BLUE.length} agents acting · ${exposed} real ${exposed === 1 ? "record" : "records"} exposed`}
            className="lg:border-l lg:border-line lg:pl-5">
            <Approvals s={s} />
            <div className={`grid min-h-0 flex-1 grid-cols-1 gap-4 md:grid-cols-2 ${DEFEND}`}>
              <Vitals stats={s.stats} className="md:col-span-2 lg:col-span-1 lg:[grid-area:vitals]" />
              <Pantheon s={s} className="lg:[grid-area:pantheon]" />
              <Visitors stats={s.stats} className="lg:[grid-area:visitors]" />
              <AgentLog title="Defender messages" items={s.blue} empty="Hermes carries every defender's thoughts, actions and alerts here."
                onOpen={() => openTab("Agents")} className="h-[400px] md:col-span-2 lg:col-span-1 lg:h-auto lg:min-h-0 lg:[grid-area:defenders]" />
            </div>
          </Side>
        </div>
        <Drawer s={s} open={open} tab={tab} onTab={setTab} onClose={close} picked={picked} onPick={setPicked} />
      </main>
    </div>
  );
}
