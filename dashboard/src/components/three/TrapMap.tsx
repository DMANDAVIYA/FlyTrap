import { Edges, Html, Line, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { useReducedMotion } from "framer-motion";
import { useEffect, useMemo, useRef, type MutableRefObject } from "react";
import * as THREE from "three";
import { onMessage } from "@/feed";
import type { EventData } from "@/types";

type V3 = [number, number, number];
interface Dot { pts: V3[]; t0: number; dur: number; trap: boolean }
type Glow = Record<string, { t: number; color: string }>;
type Mats = Record<string, THREE.MeshStandardMaterial>;

// Olympus stands on the glass floor. Tartarus hangs beneath it: the same towers, mirrored, in red.
const POD_Y = -1.9;
const NODES: Record<string, V3> = {
  internet: [-6.4, 0.2, 0],
  charon: [-2.6, 0.02, 0],
  under: [-2.6, -1.9, 0],
  "web-1": [1.2, 0.75, -1.1], "web-2": [1.2, 0.75, 1.1], "db-real": [3.5, 0.45, 0],
  "pod-1": [1.2, POD_Y, -2.6], "pod-2": [1.2, POD_Y, -1.3], "pod-3": [1.2, POD_Y, 0], "pod-4": [1.2, POD_Y, 1.3], "pod-5": [1.2, POD_Y, 2.6],
  "backup-01": [3.5, -1.65, -1.2], "model-vault": [3.5, -1.65, 1.2],
};
const PODS = ["pod-1", "pod-2", "pod-3", "pod-4", "pod-5"];
const MAX_DOTS = 240;
const C = { real: "#4c8dff", trap: "#ff3355", warn: "#ffb020", ok: "#00ff66", dim: "#86a593" };

const entry = (name: string, dx = -0.5): V3 => {
  const [x, y, z] = NODES[name];
  return [x + dx, name.startsWith("web") ? 0.35 : y, z];
};

function route(e: EventData, rr: number): { pts: V3[]; trap: boolean } {
  const start: V3 = [NODES.internet[0], NODES.internet[1], ((e.id * 37) % 100) / 20 - 2.5];
  const path = e.path ?? "";
  if (e.side === "trap" || e.side === "blocked") {
    const pod = NODES[e.pod ?? ""] ? e.pod! : "pod-1";
    const pts: V3[] = [start, NODES.charon, NODES.under, entry(pod), NODES[pod]];
    if (path.includes("internal-backup") || path.includes("/infra/backup-01")) pts.push(entry("backup-01", -0.45), NODES["backup-01"]);
    if (path.includes("/infra/model-vault")) pts.push(entry("model-vault", -0.45), NODES["model-vault"]);
    return { pts, trap: true };
  }
  const web = rr % 2 ? "web-1" : "web-2";
  return { pts: [start, NODES.charon, entry(web), NODES[web]], trap: false };
}

function along(pts: V3[], f: number): V3 {
  const segs = pts.length - 1;
  const x = Math.min(f * segs, segs - 1e-6);
  const i = Math.floor(x), t = x - i;
  const a = pts[i], b = pts[i + 1];
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

function Dots({ dots }: { dots: MutableRefObject<Dot[]> }) {
  const mesh = useRef<THREE.InstancedMesh>(null!);
  const tmp = useMemo(() => new THREE.Object3D(), []);
  const red = useMemo(() => new THREE.Color(C.trap), []);
  const blue = useMemo(() => new THREE.Color(C.real), []);

  useEffect(() => {
    for (let i = 0; i < MAX_DOTS; i++) mesh.current.setColorAt(i, blue);
  }, [blue]);

  useFrame(() => {
    const now = performance.now();
    dots.current = dots.current.filter((d) => now - d.t0 < d.dur);
    for (let i = 0; i < MAX_DOTS; i++) {
      const d = dots.current[i];
      if (d) {
        tmp.position.set(...along(d.pts, (now - d.t0) / d.dur));
        tmp.scale.setScalar(d.trap ? 1.3 : 1);
        mesh.current.setColorAt(i, d.trap ? red : blue);
      } else {
        tmp.position.set(0, -50, 0);
        tmp.scale.setScalar(0);
      }
      tmp.updateMatrix();
      mesh.current.setMatrixAt(i, tmp.matrix);
    }
    mesh.current.instanceMatrix.needsUpdate = true;
    if (mesh.current.instanceColor) mesh.current.instanceColor.needsUpdate = true;
  });

  return (
    <instancedMesh ref={mesh} args={[undefined, undefined, MAX_DOTS]} frustumCulled={false}>
      <sphereGeometry args={[0.075, 10, 10]} />
      <meshBasicMaterial toneMapped={false} />
    </instancedMesh>
  );
}

function Block({ name, size, color, mats, round = false }: { name: string; size: V3; color: string; mats: MutableRefObject<Mats>; round?: boolean }) {
  return (
    <mesh position={NODES[name]}>
      {round ? <cylinderGeometry args={[size[0] / 2, size[0] / 2, size[1], 28]} /> : <boxGeometry args={size} />}
      <meshStandardMaterial
        ref={(m: THREE.MeshStandardMaterial | null) => { if (m) mats.current[name] = m; }}
        color="#0b1a12" emissive={color} emissiveIntensity={0.18} roughness={0.4} transparent opacity={0.55} depthWrite={false}
      />
      <Edges color={color} threshold={20} />
    </mesh>
  );
}

function Label({ at, title, sub, color }: { at: V3; title: string; sub?: string; color: string }) {
  return (
    <Html position={at} center zIndexRange={[20, 0]} style={{ pointerEvents: "none" }}>
      <div className="whitespace-nowrap text-center leading-tight">
        <div className="text-[11px] font-bold uppercase tracking-[0.22em]" style={{ color, fontStretch: "118%" }}>{title}</div>
        {sub && <div className="mt-0.5 text-[11px] text-text2">{sub}</div>}
      </div>
    </Html>
  );
}

function Scene({ still }: { still: boolean }) {
  const dots = useRef<Dot[]>([]);
  const glow = useRef<Glow>({});
  const mats = useRef<Mats>({});
  const door = useRef<THREE.MeshBasicMaterial>(null!);

  useEffect(() => {
    let rr = 0;
    return onMessage((m) => {
      const now = performance.now();
      if (m.type === "event" && (m.data.kind === "request" || m.data.kind === "beacon")) {
        const r = route(m.data, rr++);
        dots.current.push({ ...r, t0: now, dur: 1300 + r.pts.length * 180 });
        if (dots.current.length > MAX_DOTS) dots.current.splice(0, dots.current.length - MAX_DOTS);
        const target = r.trap ? (NODES[m.data.pod ?? ""] ? m.data.pod! : "pod-1") : rr % 2 ? "web-2" : "web-1";
        glow.current[target] = { t: now, color: r.trap ? C.trap : C.real };
      } else if (m.type === "event" && m.data.kind === "tripwire") {
        glow.current.charon = { t: now, color: C.warn };
      } else if (m.type === "flip") {
        glow.current[m.data.pod] = { t: now, color: C.trap };
        glow.current.charon = { t: now, color: C.trap };
        glow.current.door = { t: now, color: C.trap };
      }
    });
  }, []);

  useFrame(() => {
    const now = performance.now();
    for (const [name, mat] of Object.entries(mats.current)) {
      const g = glow.current[name];
      const age = g ? (now - g.t) / 1200 : 1;
      const base = name === "charon" ? C.ok : name.startsWith("pod") || name === "backup-01" || name === "model-vault" ? C.trap : C.real;
      mat.emissive.set(age < 1 ? g!.color : base);
      mat.emissiveIntensity = 0.18 + (age < 1 ? 1.2 * (1 - age) : 0);
    }
    const d = glow.current.door;
    const age = d ? (now - d.t) / 1400 : 1;
    door.current.opacity = 0.14 + (age < 1 ? 0.6 * (1 - age) : 0);
  });

  const v = (n: string) => new THREE.Vector3(...NODES[n]);

  return (
    <>
      <fog attach="fog" args={["#030604", 13, 26]} />
      <ambientLight intensity={0.5} />
      <directionalLight position={[4, 8, 6]} intensity={0.6} />

      {/* The website's surface: a glass floor you can see through. */}
      <mesh rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[16, 16]} />
        <meshBasicMaterial color="#0a1f13" transparent opacity={0.5} depthWrite={false} side={THREE.DoubleSide} />
      </mesh>
      <gridHelper args={[16, 32, "#1f5235", "#11291b"]} position={[0, 0.002, 0]} />
      {/* Tartarus bedrock. */}
      <gridHelper args={[16, 32, "#4d1622", "#250b11"]} position={[0, -3.2, 0]} />

      {/* Charon and its trapdoor. */}
      <mesh position={NODES.charon} rotation={[Math.PI / 2, 0, 0]}>
        <torusGeometry args={[0.6, 0.05, 12, 64]} />
        <meshStandardMaterial ref={(m: THREE.MeshStandardMaterial | null) => { if (m) mats.current.charon = m; }} color="#050c08" emissive={C.ok} emissiveIntensity={0.18} />
      </mesh>
      <mesh position={[NODES.charon[0], 0.006, 0]} rotation={[-Math.PI / 2, 0, 0]}>
        <planeGeometry args={[0.9, 0.9]} />
        <meshBasicMaterial ref={door} color={C.trap} transparent opacity={0.14} depthWrite={false} toneMapped={false} />
      </mesh>

      <Block name="web-1" size={[0.8, 1.5, 0.8]} color={C.real} mats={mats} />
      <Block name="web-2" size={[0.8, 1.5, 0.8]} color={C.real} mats={mats} />
      <Block name="db-real" size={[0.9, 0.9, 0.9]} color={C.real} mats={mats} round />
      {PODS.map((p) => <Block key={p} name={p} size={[0.7, 1.3, 0.7]} color={C.trap} mats={mats} />)}
      <Block name="backup-01" size={[0.8, 0.8, 0.8]} color={C.trap} mats={mats} round />
      <Block name="model-vault" size={[0.8, 0.8, 0.8]} color={C.trap} mats={mats} round />

      <Line points={[v("internet"), v("charon")]} color={C.dim} lineWidth={1} transparent opacity={0.35} />
      {["web-1", "web-2"].map((w) => (
        <group key={w}>
          <Line points={[v("charon"), new THREE.Vector3(...entry(w))]} color={C.real} lineWidth={1} transparent opacity={0.45} />
          <Line points={[v(w), v("db-real")]} color={C.real} lineWidth={1} transparent opacity={0.3} />
        </group>
      ))}
      <Line points={[v("charon"), v("under")]} color={C.trap} lineWidth={1.2} dashed dashSize={0.12} gapSize={0.08} transparent opacity={0.7} />
      {PODS.map((p) => <Line key={p} points={[v("under"), new THREE.Vector3(...entry(p))]} color={C.trap} lineWidth={1} transparent opacity={0.35} />)}
      <Line points={[v("pod-2"), v("backup-01")]} color={C.trap} lineWidth={1} transparent opacity={0.25} />
      <Line points={[v("pod-4"), v("model-vault")]} color={C.trap} lineWidth={1} transparent opacity={0.25} />

      <Dots dots={dots} />

      <Label at={[NODES.internet[0], 0.75, 0]} title="Visitors" color={C.dim} />
      <Label at={[NODES.charon[0], 0.85, 0]} title="Charon" sub="gateway" color={C.ok} />
      <Label at={[2.4, 2.1, 0]} title="Olympus" sub="real servers" color={C.real} />
      <Label at={[2.4, -3.05, 0]} title="Tartarus" sub="the copy · fake data · no route out" color={C.trap} />

      <OrbitControls
        target={[-0.7, -0.6, 0]}
        enablePan={false}
        enableDamping
        minDistance={7}
        maxDistance={17}
        minPolarAngle={0.55}
        maxPolarAngle={1.62}
        autoRotate={!still}
        autoRotateSpeed={0.3}
      />
    </>
  );
}

/** The trap made visible: every visitor enters through Charon and either reaches Olympus or drops into Tartarus. */
export default function TrapMap() {
  const still = !!useReducedMotion();
  return (
    <Canvas
      dpr={[1, 1.5]}
      camera={{ position: [-5.6, 2.4, 10.2], fov: 42 }}
      gl={{ antialias: true, alpha: true }}
      flat
      fallback={<p className="p-6 text-text2 text-sm">The 3D map needs WebGL. Sessions and vitals still update on the right.</p>}
    >
      <Scene still={still} />
    </Canvas>
  );
}
