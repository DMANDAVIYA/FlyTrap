import { useCallback, useEffect, useState } from "react";
import { Approvals } from "@/components/Approvals";
import { Activity } from "@/components/console/Activity";
import { Gateway } from "@/components/console/Gateway";
import { Kpis } from "@/components/console/Kpis";
import { Pantheon } from "@/components/console/Pantheon";
import { Traffic } from "@/components/console/Traffic";
import { Visitors } from "@/components/console/Visitors";
import { Drawer, type Tab } from "@/components/Drawer";
import { FlipToast } from "@/components/FlipToast";
import { LockdownOverlay } from "@/components/Lockdown";
import { RawConsole } from "@/components/raw/RawConsole";
import { TopBar } from "@/components/TopBar";
import { useFeed } from "@/feed";

// Two rows on laptops, fixed to the viewport: traffic beside six readings, then visitors, the pantheon
// over the gateway, and the working table. One column (two on tablets) with normal scrolling below lg.
// Rows never shrink below what their cards need; a short screen scrolls the grid instead of clipping cards.
const GRID = "md:grid-cols-2 lg:grid-cols-12 lg:grid-rows-[minmax(280px,1fr)_minmax(330px,1.1fr)]";

export default function Console() {
  const s = useFeed();
  const [picked, setPicked] = useState<string | null>(null);
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("Agents");
  const lockdown = s.lockdown.state !== "off";
  // Raw view: the same feed as a terminal UI. Remembered per browser; storage can be unavailable.
  const [raw, setRaw] = useState(() => {
    try { return localStorage.getItem("dolos.view") === "raw"; } catch { return false; }
  });
  useEffect(() => {
    try { localStorage.setItem("dolos.view", raw ? "raw" : "cards"); } catch { /* private mode */ }
  }, [raw]);

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
    <div className={`console-ui flex min-h-[100svh] flex-col bg-bg text-text lg:h-[100svh] ${raw ? "tui" : ""} ${lockdown ? "outline outline-4 -outline-offset-4 outline-warn/60" : ""}`}>
      <h1 className="sr-only">Dolos console</h1>
      <LockdownOverlay lock={s.lockdown} />
      <TopBar s={s} drawerOpen={open} onToggleDrawer={() => setOpen((o) => !o)} raw={raw} onToggleRaw={() => setRaw((r) => !r)} />
      <FlipToast s={s} />
      {/* overflow-x-clip: the drawer slides in from the right edge without widening the page. */}
      <main className="relative flex min-h-0 flex-1 flex-col overflow-x-clip">
        <div className="flex min-h-0 flex-1 flex-col gap-4 p-4 scroll-thin sm:p-5 lg:overflow-y-auto">
          {raw ? <RawConsole s={s} picked={picked} onPick={openReport} /> : <>
            <Approvals s={s} />
            <div className={`grid min-h-0 flex-1 grid-cols-1 gap-4 ${GRID}`}>
              <Traffic rps={s.rps} className="min-h-[360px] md:col-span-2 lg:col-span-6 lg:min-h-0" />
              <Kpis s={s} className="md:col-span-2 lg:col-span-6" />
              <Visitors stats={s.stats} className="min-h-[320px] md:col-span-2 lg:col-span-3 lg:min-h-0" />
              <div className="flex min-h-0 flex-col gap-4 lg:col-span-4">
                <Pantheon s={s} />
                <Gateway hist={s.hist} requests={s.stats.requests_total} className="min-h-[200px] flex-1 lg:min-h-0" />
              </div>
              <Activity s={s} picked={picked} onOpen={openReport}
                className="h-[520px] md:col-span-2 lg:col-span-5 lg:h-auto lg:min-h-0" />
            </div>
          </>}
        </div>
        <Drawer s={s} open={open} tab={tab} onTab={setTab} onClose={close} picked={picked} onPick={setPicked} />
      </main>
    </div>
  );
}
