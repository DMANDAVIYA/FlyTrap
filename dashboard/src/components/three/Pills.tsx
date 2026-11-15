import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { useReducedMotion } from "framer-motion";
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";

export type PillId = "blue" | "red";
const COLOR: Record<PillId, string> = { blue: "#1747e0", red: "#e0102f" };

// Local studio reflections: no HDR download, so it works on venue wifi.
function Studio() {
  const gl = useThree((s) => s.gl);
  const scene = useThree((s) => s.scene);
  useEffect(() => {
    const pmrem = new THREE.PMREMGenerator(gl);
    const room = new RoomEnvironment();
    const env = pmrem.fromScene(room, 0.04).texture;
    scene.environment = env;
    return () => {
      scene.environment = null;
      env.dispose();
      room.dispose();
      pmrem.dispose();
    };
  }, [gl, scene]);
  return null;
}

interface PillProps {
  id: PillId;
  hovered: boolean;
  still: boolean;
  onHover: (p: PillId | null) => void;
  onPick: (p: PillId) => void;
}

function Pill({ id, hovered, still, onHover, onPick }: PillProps) {
  const width = useThree((s) => s.viewport.width);
  const sway = useRef<THREE.Group>(null!);
  const body = useRef<THREE.Group>(null!);
  const mat = useRef<THREE.MeshPhysicalMaterial>(null!);
  const x = (id === "blue" ? -1 : 1) * Math.min(width / 4, 1.9);

  useFrame((state, dt) => {
    if (still) return;
    body.current.scale.setScalar(THREE.MathUtils.damp(body.current.scale.x, hovered ? 1.14 : 1, 10, dt));
    mat.current.emissiveIntensity = THREE.MathUtils.damp(mat.current.emissiveIntensity, hovered ? 0.5 : 0.16, 8, dt);
    const t = state.clock.elapsedTime + (id === "red" ? 1.7 : 0);
    sway.current.position.y = Math.sin(t * 1.1) * 0.08;
    sway.current.rotation.y = Math.sin(t * 0.55) * 0.7 + state.pointer.x * 0.35;
    sway.current.rotation.x = -state.pointer.y * 0.25;
  });

  return (
    <group position={[x, 0, 0]}>
      <group ref={sway}>
        <group ref={body} rotation={[0, 0, id === "blue" ? 0.55 : -0.55]} scale={still && hovered ? 1.14 : 1}>
          <mesh
            onPointerOver={(e) => {
              e.stopPropagation();
              onHover(id);
            }}
            onPointerOut={() => onHover(null)}
            onClick={(e) => {
              e.stopPropagation();
              onPick(id);
            }}
          >
            <capsuleGeometry args={[0.42, 1.05, 12, 40]} />
            <meshPhysicalMaterial
              ref={mat}
              color={COLOR[id]}
              emissive={COLOR[id]}
              emissiveIntensity={still && hovered ? 0.5 : 0.16}
              roughness={0.22}
              clearcoat={1}
              clearcoatRoughness={0.03}
              envMapIntensity={0.7}
            />
          </mesh>
        </group>
      </group>
    </group>
  );
}

/** The red pill and the blue pill. Real links sit beside them; mesh clicks are an extra. */
export default function Pills({
  hovered,
  onHover,
  onPick,
}: {
  hovered: PillId | null;
  onHover: (p: PillId | null) => void;
  onPick: (p: PillId) => void;
}) {
  const still = !!useReducedMotion();
  const wrap = useRef<HTMLDivElement>(null);
  const [onScreen, setOnScreen] = useState(true);

  useEffect(() => {
    const io = new IntersectionObserver(([e]) => setOnScreen(e.isIntersecting));
    if (wrap.current) io.observe(wrap.current);
    return () => io.disconnect();
  }, []);

  useEffect(() => {
    document.body.style.cursor = hovered ? "pointer" : "";
    return () => {
      document.body.style.cursor = "";
    };
  }, [hovered]);

  return (
    <div ref={wrap} className="absolute inset-0">
      <Canvas
        dpr={[1, 1.75]}
        camera={{ position: [0, 0, 5], fov: 35 }}
        frameloop={onScreen && !still ? "always" : "demand"}
        gl={{ antialias: true, alpha: true }}
        flat
        fallback={null}
      >
        <Studio />
        <ambientLight intensity={0.25} />
        <directionalLight position={[2.5, 3, 4]} intensity={1.4} />
        <directionalLight position={[-3, -1, 2]} intensity={0.4} color="#88ffbb" />
        {(["blue", "red"] as const).map((id) => (
          <Pill key={id} id={id} hovered={hovered === id} still={still} onHover={onHover} onPick={onPick} />
        ))}
      </Canvas>
    </div>
  );
}
