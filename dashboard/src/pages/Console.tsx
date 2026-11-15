import { useCallback, useEffect, useState } from "react";
import { Approvals } from "@/components/Approvals";
import { Counters } from "@/components/Counters";
import { Drawer, type Tab } from "@/components/Drawer";
import { LiveMap } from "@/components/LiveMap";
import { LockdownOverlay } from "@/components/Lockdown";
import { Sessions } from "@/components/Sessions";
import { TopBar } from "@/components/TopBar";
import { useFeed } from "@/feed";

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
  const openReport = (sid: string) => {
    setPicked(sid);
    setTab("Report");
    setOpen(true);
  };

  return (
    <div className={`flex h-[100svh] min-h-[620px] flex-col bg-bg ${lockdown ? "outline outline-4 outline-warn/60 -outline-offset-4" : ""}`}>
      <LockdownOverlay lock={s.lockdown} />
      <TopBar s={s} drawerOpen={open} onToggleDrawer={() => setOpen((o) => !o)} />
      {/* overflow-x-clip: the drawer slides in from the right edge without widening the page. */}
      <div className="relative grid min-h-0 flex-1 overflow-x-clip grid-rows-[minmax(360px,1fr)_auto] lg:grid-rows-1 lg:grid-cols-[minmax(0,1fr)_360px]">
        <LiveMap s={s} />
        <aside className="flex min-h-0 flex-col border-t border-line lg:border-t-0 lg:border-l" aria-label="Containment">
          <Counters stats={s.stats} />
          <Approvals s={s} />
          <Sessions s={s} picked={picked} onPick={openReport} />
        </aside>
        <Drawer s={s} open={open} tab={tab} onTab={setTab} onClose={close} picked={picked} onPick={setPicked} />
      </div>
    </div>
  );
}
