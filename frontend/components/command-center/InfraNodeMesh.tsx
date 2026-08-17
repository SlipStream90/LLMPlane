"use client";

import { useRef } from "react";
import { useFrame, type ThreeEvent } from "@react-three/fiber";
import { Html } from "@react-three/drei";
import * as THREE from "three";
import type { InfraNode, NodeState } from "./types";

export const STATE_COLORS: Record<NodeState, string> = {
  healthy: "#22c55e",
  "high-load": "#eab308",
  warning: "#f59e0b",
  critical: "#ef4444",
  offline: "#64748b",
};

export const STATE_LABEL: Record<NodeState, string> = {
  healthy: "Healthy",
  "high-load": "High Load",
  warning: "Warning",
  critical: "Critical",
  offline: "Offline",
};

interface Props {
  node: InfraNode;
  selected: boolean;
  hovered: boolean;
  dimmed: boolean;
  reduceMotion: boolean;
  onSelect: (id: string) => void;
  onHover: (id: string | null) => void;
}

export function InfraNodeMesh({
  node,
  selected,
  hovered,
  dimmed,
  reduceMotion,
  onSelect,
  onHover,
}: Props) {
  const groupRef = useRef<THREE.Group>(null);
  const matRef = useRef<THREE.MeshStandardMaterial>(null);
  const ringRef = useRef<THREE.MeshBasicMaterial>(null);
  const color = STATE_COLORS[node.state];

  useFrame((state) => {
    const t = state.clock.elapsedTime;
    let scale = 1;
    if (node.state === "warning" || node.state === "critical") {
      const amp = reduceMotion ? 0.03 : 0.1;
      const speed = node.state === "critical" ? 8 : 4;
      scale = 1 + amp * Math.sin(t * speed);
    }
    if (hovered) scale *= 1.28;
    if (selected) scale *= 1.15;
    groupRef.current?.scale.setScalar(scale);

    if (matRef.current) {
      const target =
        node.state === "offline"
          ? 0.15
          : node.state === "critical"
          ? 1.7
          : node.state === "warning"
          ? 1.1
          : 0.6;
      matRef.current.emissiveIntensity +=
        (target - matRef.current.emissiveIntensity) * 0.1;
    }
    if (ringRef.current) {
      const targetOpacity = dimmed ? 0.12 : hovered || selected ? 0.9 : 0.5;
      ringRef.current.opacity += (targetOpacity - ringRef.current.opacity) * 0.1;
    }
  });

  return (
    <group position={node.position}>
      <group
        ref={groupRef}
        onClick={(e: ThreeEvent<MouseEvent>) => {
          e.stopPropagation();
          onSelect(node.id);
        }}
        onPointerOver={(e: ThreeEvent<PointerEvent>) => {
          e.stopPropagation();
          onHover(node.id);
          document.body.style.cursor = "pointer";
        }}
        onPointerOut={(e: ThreeEvent<PointerEvent>) => {
          e.stopPropagation();
          onHover(null);
          document.body.style.cursor = "auto";
        }}
      >
        <mesh>
          <icosahedronGeometry args={[0.7, 1]} />
          <meshStandardMaterial
            ref={matRef}
            color={color}
            emissive={color}
            emissiveIntensity={0.6}
            roughness={0.3}
            metalness={0.4}
            transparent
            opacity={node.state === "offline" ? 0.45 : 1}
          />
        </mesh>
        <mesh rotation={[Math.PI / 2, 0, 0]}>
          <torusGeometry args={[1.05, 0.035, 10, 56]} />
          <meshBasicMaterial
            ref={ringRef}
            color={color}
            transparent
            opacity={0.5}
          />
        </mesh>
      </group>

      <Html
        position={[0, 1.5, 0]}
        center
        distanceFactor={14}
        style={{ pointerEvents: "none", userSelect: "none" }}
      >
        <div
          className="px-2 py-0.5 rounded-md text-[11px] font-medium whitespace-nowrap border backdrop-blur-sm"
          style={{
            color,
            borderColor: `${color}55`,
            background: "rgba(8,12,20,0.72)",
            opacity: dimmed ? 0.5 : 1,
          }}
        >
          {node.label}
        </div>
      </Html>
    </group>
  );
}
