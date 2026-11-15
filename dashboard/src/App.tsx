import { lazy, Suspense, useEffect, useRef, useState } from "react";
import Landing from "./pages/Landing";

const Console = lazy(() => import("./pages/Console"));
const BotView = lazy(() => import("./pages/BotView"));

// Hash routes: dash-api has no SPA fallback, so "#/console" works on any static host.
const routeOf = (hash: string) => (hash.startsWith("#/console") ? "console" : hash.startsWith("#/see") ? "see" : "landing");

export default function App() {
  const [route, setRoute] = useState(() => routeOf(location.hash));
  const first = useRef(true);

  useEffect(() => {
    const onHash = () => setRoute(routeOf(location.hash));
    addEventListener("hashchange", onHash);
    return () => removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    if (first.current) first.current = false;
    else window.scrollTo(0, 0);
  }, [route]);

  if (route === "landing") return <Landing />;
  return (
    <Suspense fallback={<div className="h-screen bg-bg" />}>
      {route === "console" ? <Console /> : <BotView />}
    </Suspense>
  );
}
