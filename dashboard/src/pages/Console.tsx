import { useCallback, useEffect, useState } from "react";
import { Approvals } from "@/components/Approvals";
import { AgentLog } from "@/components/console/AgentLog";
import { Pantheon } from "@/components/console/Pantheon";
import { Traffic } from "@/components/console/Traffic";
import { Visitors } from "@/components/console/Visitors";
import { Vitals } from "@/components/console/Vitals";
import { Drawer, type Tab } from "@/components/Drawer";
import { FlipToast } from "@/components/FlipToast";
import { LockdownOverlay } from "@/components/Lockdown";
import { Sessions } from "@/components/Sessions";
import { TopBar } from "@/components/TopBar";
import { useFeed } from "@/feed";

// Bento: four columns on laptops, fixed to the viewport; two columns and normal scrolling below lg.
const GRID = "lg:grid-cols-4 lg:grid-rows-[minmax(0,1fr)_minmax(0,1fr)_minmax(0,1fr)] " +
  "lg:[grid-template-areas:'vitals_vitals_traffic_traffic''trapped_visitors_log_log''trapped_pantheon_log_log']";

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

  return (
    <div className={`flex min-h-[100svh] flex-col bg-bg lg:h-[100svh] ${lockdown ? "outline outline-4 -outline-offset-4 outline-warn/60" : ""}`}>
      <h1 className="sr-only">Dolos console</h1>
      <LockdownOverlay lock={s.lockdown} />
      <TopBar s={s} drawerOpen={open} onToggleDrawer={() => setOpen((o) => !o)} />
      <FlipToast s={s} />
      {/* overflow-x-clip: the drawer slides in from the right edge without widening the page. */}
      <main className="relative flex min-h-0 flex-1 flex-col gap-4 overflow-x-clip p-4 sm:p-5">
        <Approvals s={s} />
        <div className={`grid min-h-0 flex-1 grid-cols-1 gap-4 md:grid-cols-2 ${GRID}`}>
          <Vitals stats={s.stats} className="md:col-span-2 lg:col-span-1 lg:[grid-area:vitals]" />
          <Traffic rps={s.rps} stats={s.stats} className="min-h-[300px] md:col-span-2 lg:col-span-1 lg:min-h-0 lg:[grid-area:traffic]" />
          <Sessions s={s} picked={picked} onPick={openReport} className="min-h-[320px] lg:min-h-0 lg:[grid-area:trapped]" />
          <Visitors stats={s.stats} className="lg:[grid-area:visitors]" />
          <AgentLog s={s} onOpen={() => openTab("Agents")} className="min-h-[320px] md:col-span-2 lg:col-span-1 lg:min-h-0 lg:[grid-area:log]" />
          <Pantheon s={s} className="lg:[grid-area:pantheon]" />
        </div>
        <Drawer s={s} open={open} tab={tab} onTab={setTab} onClose={close} picked={picked} onPick={setPicked} />
      </main>
    </div>
  );
}
