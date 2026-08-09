"use client";

import { useMemo, useRef } from "react";
import { useFrame } from "@react-three/fiber";
import * as THREE from "three";
import type { InfraNode } from "./types";
import type { LiveTrafficRefs } from "./useLiveTraffic";

interface Particle {
  curve: THREE.CatmullRomCurve3;
  t: number;
  speed: number;
  status: "success" | "error";
}

const CAPACITY = 280;

interface Props {
  nodes: InfraNode[];
  traffic: LiveTrafficRefs;
}

/**
 * Instanced particle stream. Each live request becomes a moving point that
 * travels clients -> gateway -> provider -> evaluation -> database. Particle
 * counts are bounded (instanced) and the emission rate is driven by
 * `useLiveTraffic` (real gateway events, or a synthetic fallback).
 */
export function RequestParticles({ nodes, traffic }: Props) {
  const meshRef = useRef<THREE.InstancedMesh>(null);
  const particles = useRef<Particle[]>([]);
  const accumulator = useRef(0);
  const dummy = useMemo(() => new THREE.Object3D(), []);
  const color = useMemo(() => new THREE.Color(), []);

  const posMap = useMemo(() => {
    const m = new Map<string, THREE.Vector3>();
    for (const n of nodes) m.set(n.id, new THREE.Vector3(...n.position));
    return m;
  }, [nodes]);

  const pathPoints = useMemo(
    () => ({
      clients: posMap.get("clients")!,
      gateway: posMap.get("gateway")!,
      evaluation: posMap.get("evaluation")!,
      database: posMap.get("database")!,
    }),
    [posMap]
  );

  useFrame((_, delta) => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const dt = Math.min(delta, 0.05);

    // Spawn based on the live rate.
    const rate = traffic.rateRef.current;
    accumulator.current += rate * dt;
    const ids = traffic.nodesRef.current;
    while (accumulator.current >= 1 && particles.current.length < CAPACITY) {
      accumulator.current -= 1;
      if (!ids.length) break;
      const pid = ids[Math.floor(Math.random() * ids.length)];
      const providerPos = posMap.get(pid) ?? pathPoints.gateway;
      const curve = new THREE.CatmullRomCurve3([
        pathPoints.clients,
        pathPoints.gateway,
        providerPos,
        pathPoints.evaluation,
        pathPoints.database,
      ]);
      const status = Math.random() < 0.06 ? "error" : "success";
      const speed = 0.18 + Math.random() * 0.12;
      particles.current.push({ curve, t: 0, speed, status });
    }

    // Advance + render.
    particles.current = particles.current.filter((p) => {
      p.t += p.speed * dt;
      return p.t < 1;
    });

    for (let i = 0; i < CAPACITY; i++) {
      const p = particles.current[i];
      if (!p) {
        dummy.scale.setScalar(0);
        dummy.position.set(0, 0, 0);
        dummy.updateMatrix();
        mesh.setMatrixAt(i, dummy.matrix);
        continue;
      }
      const pt = p.curve.getPoint(p.t);
      dummy.position.copy(pt);
      dummy.scale.setScalar(0.16);
      dummy.updateMatrix();
      mesh.setMatrixAt(i, dummy.matrix);
      color.set(p.status === "error" ? "#ef4444" : "#38bdf8");
      mesh.setColorAt(i, color);
    }

    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, CAPACITY]}>
      <sphereGeometry args={[1, 10, 10]} />
      <meshBasicMaterial toneMapped={false} />
    </instancedMesh>
  );
}
