import { lazy, Suspense, useEffect, useRef, useState } from "react";
import Landing from "./pages/Landing";

const Console = lazy(() => import("./pages/Console"));

// Hash routes: dash-api has no SPA fallback, so "#/console" works on any static host.
const routeOf = (hash: string) => (hash.startsWith("#/console") ? "console" : "landing");

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

  return route === "console" ? (
    <Suspense fallback={<div className="h-screen bg-bg" />}>
      <Console />
    </Suspense>
  ) : (
    <Landing />
  );
}
