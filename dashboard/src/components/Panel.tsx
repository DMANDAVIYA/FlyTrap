import { MessageSquare, PenLine, TriangleAlert, Wrench } from "lucide-react";
import type { ReactNode } from "react";

const KIND_ICON = { thought: MessageSquare, action: Wrench, note: PenLine, alert: TriangleAlert };

/** Drawn icon for a log line kind, at the stroke weight the rest of the UI uses. */
export function KindIcon({ kind, className = "" }: { kind: string; className?: string }) {
  const Icon = KIND_ICON[kind as keyof typeof KIND_ICON] ?? MessageSquare;
  return <Icon size={11} strokeWidth={1.8} aria-label={kind} className={`inline-block -translate-y-px ${className}`} />;
}

export function Panel({ title, right, children, className = "", bodyClass = "" }: {
  title: string; right?: ReactNode; children: ReactNode; className?: string; bodyClass?: string;
}) {
  return (
    <section className={`panel flex flex-col min-h-0 ${className}`}>
      <header className="flex items-center justify-between px-4 py-2.5 border-b border-line">
        <h2 className="panel-title">{title}</h2>
        {right}
      </header>
      <div className={`flex-1 min-h-0 ${bodyClass}`}>{children}</div>
    </section>
  );
}

export const agentColor = (agent: string) =>
  ({
    // Defenders in greens, raiders in neutral greys: the log stays black and green.
    athena: "#e4f0e8", argus: "#9fe8c3", hephaestus: "#c8dc8f", cerberus: "#5fd39a", mnemosyne: "#b3c7bb",
    clio: "#d6e6a6", hermes: "#3dff8f", zeus: "#ffffff", charon: "#8aa293",
    prometheus: "#d9dfdb", pandora: "#c3cbc6", odysseus: "#d9dfdb", icarus: "#c3cbc6", sisyphus: "#aeb7b1",
  })[agent] ?? "#93a3af";

export const sideColor = (side?: string | null) => (side === "trap" || side === "blocked" ? "var(--trap)" : "var(--real)");

export function clock(t: number | string) {
  const d = typeof t === "number" ? new Date(t) : new Date(t);
  return d.toLocaleTimeString([], { hour12: false });
}

/** s_43e8c951b7b8a201 -> s_43e8c9 (full id in the title attribute). */
export const short = (sid?: string | null) => (sid && sid.length > 9 ? sid.slice(0, 8) : sid ?? "");
