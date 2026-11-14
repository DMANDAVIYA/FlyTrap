import type { ReactNode } from "react";

export function Panel({ title, right, children, className = "", bodyClass = "" }: {
  title: string; right?: ReactNode; children: ReactNode; className?: string; bodyClass?: string;
}) {
  return (
    <section className={`panel flex flex-col min-h-0 ${className}`}>
      <header className="flex items-center justify-between px-3 py-2 border-b border-line">
        <h2 className="panel-title">{title}</h2>
        {right}
      </header>
      <div className={`flex-1 min-h-0 ${bodyClass}`}>{children}</div>
    </section>
  );
}

export const agentColor = (agent: string) =>
  ({
    athena: "#c9b8ff", argus: "#7fd4ff", hephaestus: "#ffb36b", cerberus: "#ff8a8a", mnemosyne: "#b8e986",
    clio: "#f5d76e", hermes: "#9ef0e0", zeus: "#ffffff", charon: "#93a3af",
    prometheus: "#ff6b4a", pandora: "#ff4fa3", odysseus: "#ffa94d", icarus: "#ff4747", sisyphus: "#d97757",
  })[agent] ?? "#93a3af";

export const sideColor = (side?: string | null) => (side === "trap" || side === "blocked" ? "var(--trap)" : "var(--real)");

export function clock(t: number | string) {
  const d = typeof t === "number" ? new Date(t) : new Date(t);
  return d.toLocaleTimeString([], { hour12: false });
}

/** s_43e8c951b7b8a201 -> s_43e8c9 (full id in the title attribute). */
export const short = (sid?: string | null) => (sid && sid.length > 9 ? sid.slice(0, 8) : sid ?? "");
