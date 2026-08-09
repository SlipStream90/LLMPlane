"use client";

import { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Line } from "@react-three/drei";
import { EffectComposer, Bloom, Vignette } from "@react-three/postprocessing";
import * as THREE from "three";
import type { CameraMode, InfraEdge, InfraNode } from "./types";
import { InfraNodeMesh, STATE_COLORS } from "./InfraNodeMesh";
import { RequestParticles } from "./RequestParticles";
import type { LiveTrafficRefs } from "./useLiveTraffic";

interface SceneProps {
  nodes: InfraNode[];
  edges: InfraEdge[];
  selectedId: string | null;
  hoveredId: string | null;
  cameraMode: CameraMode;
  reduceMotion: boolean;
  onSelect: (id: string | null) => void;
  onHover: (id: string | null) => void;
  traffic: LiveTrafficRefs;
}

const CAMERA_PRESETS: Record<CameraMode, { pos: [number, number, number]; look: [number, number, number] }> = {
  overview: { pos: [2, 7, 26], look: [0, 0, 0] },
  gateway: { pos: [-6.5, 1, 13], look: [-6.5, 0, 0] },
  models: { pos: [0, 0.5, 17], look: [0, 0, 0] },
  observability: { pos: [5, 5, 13], look: [5, 3, 0] },
  gpu: { pos: [-6.5, -1.5, 12], look: [-6.5, -4, 0] },
  deployment: { pos: [0, -1, 17], look: [0, 0, 0] },
};

function CameraController({
  mode,
  controlsRef,
}: {
  mode: CameraMode;
  controlsRef: React.MutableRefObject<any>;
}) {
  const { camera } = useThree();
  const desired = useRef<{ pos: THREE.Vector3; look: THREE.Vector3 } | null>(null);
  const transitioning = useRef(false);

  useEffect(() => {
    const p = CAMERA_PRESETS[mode];
    desired.current = {
      pos: new THREE.Vector3(...p.pos),
      look: new THREE.Vector3(...p.look),
    };
    transitioning.current = true;
  }, [mode]);

  useFrame(() => {
    if (!transitioning.current || !desired.current) return;
    camera.position.lerp(desired.current.pos, 0.06);
    if (controlsRef.current) {
      controlsRef.current.target.lerp(desired.current.look, 0.06);
      controlsRef.current.update();
    }
    if (camera.position.distanceTo(desired.current.pos) < 0.4) {
      transitioning.current = false;
    }
  });

  return null;
}

function Edges({
  edges,
  posMap,
  hoveredId,
  selectedId,
}: {
  edges: InfraEdge[];
  posMap: Map<string, THREE.Vector3>;
  hoveredId: string | null;
  selectedId: string | null;
}) {
  const focus = hoveredId ?? selectedId;
  return (
    <>
      {edges.map((e) => {
        const from = posMap.get(e.from);
        const to = posMap.get(e.to);
        if (!from || !to) return null;
        const connected = focus && (e.from === focus || e.to === focus);
        const isRequest = e.kind === "request";
        const color = connected
          ? "#38bdf8"
          : isRequest
          ? "#3b82f6"
          : "#334155";
        const opacity = connected ? 0.85 : focus ? 0.12 : isRequest ? 0.35 : 0.22;
        return (
          <Line
            key={e.id}
            points={[from, to]}
            color={color}
            lineWidth={connected ? 2 : isRequest ? 1.4 : 1}
            transparent
            opacity={opacity}
            dashed={false}
          />
        );
      })}
    </>
  );
}

function Scene({
  nodes,
  edges,
  selectedId,
  hoveredId,
  cameraMode,
  reduceMotion,
  onSelect,
  onHover,
  traffic,
}: SceneProps) {
  const controlsRef = useRef<any>(null);

  const posMap = useMemo(() => {
    const m = new Map<string, THREE.Vector3>();
    for (const n of nodes) m.set(n.id, new THREE.Vector3(...n.position));
    return m;
  }, [nodes]);

  const focus = hoveredId ?? selectedId;
  const highlightSet = useMemo(() => {
    if (!focus) return null;
    const set = new Set<string>([focus]);
    for (const e of edges) {
      if (e.from === focus) set.add(e.to);
      if (e.to === focus) set.add(e.from);
    }
    return set;
  }, [focus, edges]);

  return (
    <>
      <color attach="background" args={["#05070d"]} />
      <ambientLight intensity={0.6} />
      <pointLight position={[10, 12, 10]} intensity={120} color="#9bd1ff" />
      <pointLight position={[-12, -6, 6]} intensity={60} color="#6366f1" />

      <gridHelper
        args={[60, 30, "#1e293b", "#0f172a"]}
        position={[0, -6, 0]}
      />

      <Edges
        edges={edges}
        posMap={posMap}
        hoveredId={hoveredId}
        selectedId={selectedId}
      />

      {nodes.map((n) => (
        <InfraNodeMesh
          key={n.id}
          node={n}
          selected={selectedId === n.id}
          hovered={hoveredId === n.id}
          dimmed={!!highlightSet && !highlightSet.has(n.id)}
          reduceMotion={reduceMotion}
          onSelect={onSelect}
          onHover={onHover}
        />
      ))}

      <RequestParticles nodes={nodes} traffic={traffic} />

      <OrbitControls
        ref={controlsRef}
        enablePan
        minDistance={6}
        maxDistance={48}
        maxPolarAngle={Math.PI / 1.8}
      />
      <CameraController mode={cameraMode} controlsRef={controlsRef} />

      {!reduceMotion && (
        <EffectComposer>
          <Bloom intensity={0.7} luminanceThreshold={0.2} luminanceSmoothing={0.9} mipmapBlur />
          <Vignette eskil={false} offset={0.25} darkness={0.75} />
        </EffectComposer>
      )}
    </>
  );
}

export function Scene3D(props: SceneProps) {
  return (
    <Canvas
      camera={{ position: [2, 7, 26], fov: 50 }}
      dpr={[1, 1.8]}
      gl={{ antialias: true, powerPreference: "high-performance" }}
      onPointerMissed={() => props.onSelect(null)}
    >
      <Scene {...props} />
    </Canvas>
  );
}

export { STATE_COLORS };
