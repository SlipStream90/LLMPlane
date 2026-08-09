"use client";

import { useEffect, useRef } from "react";
import type { InfraEdge, InfraNode, NodeState } from "./types";
import { STATE_COLORS } from "./InfraNodeMesh";
import type { LiveTrafficRefs } from "./useLiveTraffic";

interface Props {
  nodes: InfraNode[];
  edges: InfraEdge[];
  selectedId: string | null;
  hoveredId: string | null;
  reduceMotion: boolean;
  onSelect: (id: string | null) => void;
  onHover: (id: string | null) => void;
  traffic: LiveTrafficRefs;
}

interface P2D {
  ids: string[];
  t: number;
  speed: number;
  status: "success" | "error";
}

const PATH = ["clients", "gateway", "__provider__", "evaluation", "database"];

export function Scene2D({
  nodes,
  edges,
  selectedId,
  hoveredId,
  onSelect,
  onHover,
  traffic,
}: Props) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const stateRef = useRef({ selectedId, hoveredId });
  stateRef.current = { selectedId, hoveredId };
  const onSelectRef = useRef(onSelect);
  const onHoverRef = useRef(onHover);
  onSelectRef.current = onSelect;
  onHoverRef.current = onHover;

  useEffect(() => {
    const canvas = canvasRef.current!;
    const ctx = canvas.getContext("2d")!;
    const posMap = new Map<string, { x: number; y: number; z: number }>();
    for (const n of nodes) posMap.set(n.id, { x: n.position[0], y: n.position[1], z: n.position[2] });

    const particles: P2D[] = [];
    let acc = 0;
    let last = performance.now();
    let raf = 0;

    const project = (id: string, w: number, h: number, scale: number, cx: number, cy: number) => {
      const p = posMap.get(id)!;
      return { x: cx + p.x * scale, y: cy - p.y * scale };
    };

    const pick = (mx: number, my: number) => {
      const { width, height } = canvas;
      const scale = Math.min(width, height) / 30;
      const cx = width / 2;
      const cy = height / 2;
      let best: string | null = null;
      let bestD = 26;
      for (const n of nodes) {
        const s = project(n.id, width, height, scale, cx, cy);
        const d = Math.hypot(s.x - mx, s.y - my);
        if (d < bestD) {
          bestD = d;
          best = n.id;
        }
      }
      return best;
    };

    const draw = () => {
      const now = performance.now();
      const dt = Math.min((now - last) / 1000, 0.05);
      last = now;
      const { width, height } = canvas;
      const scale = Math.min(width, height) / 30;
      const cx = width / 2;
      const cy = height / 2;
      const focus = stateRef.current.hoveredId ?? stateRef.current.selectedId;

      ctx.clearRect(0, 0, width, height);

      // Edges
      const neighborSet = new Set<string>();
      if (focus) {
        neighborSet.add(focus);
        for (const e of edges) {
          if (e.from === focus) neighborSet.add(e.to);
          if (e.to === focus) neighborSet.add(e.from);
        }
      }
      for (const e of edges) {
        const a = project(e.from, width, height, scale, cx, cy);
        const b = project(e.to, width, height, scale, cx, cy);
        const connected = focus && (e.from === focus || e.to === focus);
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.strokeStyle = connected
          ? "rgba(56,189,248,0.9)"
          : focus
          ? "rgba(51,65,85,0.15)"
          : e.kind === "request"
          ? "rgba(59,130,246,0.4)"
          : "rgba(51,65,85,0.3)";
        ctx.lineWidth = connected ? 2 : 1;
        ctx.stroke();
      }

      // Spawn particles
      acc += traffic.rateRef.current * dt;
      const ids = traffic.nodesRef.current;
      while (acc >= 1 && particles.length < 140) {
        acc -= 1;
        if (!ids.length) break;
        const pid = ids[Math.floor(Math.random() * ids.length)];
        particles.push({
          ids: PATH.map((x) => (x === "__provider__" ? pid : x)),
          t: 0,
          speed: 0.22 + Math.random() * 0.14,
          status: Math.random() < 0.06 ? "error" : "success",
        });
      }

      // Particles
      for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.t += p.speed * dt;
        if (p.t >= 1) {
          particles.splice(i, 1);
          continue;
        }
        const segs = p.ids.length - 1;
        const fp = p.t * segs;
        const seg = Math.min(Math.floor(fp), segs - 1);
        const localT = fp - seg;
        const a = project(p.ids[seg], width, height, scale, cx, cy);
        const b = project(p.ids[seg + 1], width, height, scale, cx, cy);
        const x = a.x + (b.x - a.x) * localT;
        const y = a.y + (b.y - a.y) * localT;
        ctx.beginPath();
        ctx.arc(x, y, 3.2, 0, Math.PI * 2);
        ctx.fillStyle = p.status === "error" ? "#ef4444" : "#38bdf8";
        ctx.shadowColor = ctx.fillStyle;
        ctx.shadowBlur = 10;
        ctx.fill();
        ctx.shadowBlur = 0;
      }

      // Nodes
      for (const n of nodes) {
        const s = project(n.id, width, height, scale, cx, cy);
        const dim = focus && !neighborSet.has(n.id);
        const selected = stateRef.current.selectedId === n.id;
        const color = STATE_COLORS[n.state];
        ctx.beginPath();
        ctx.arc(s.x, s.y, selected ? 13 : 10, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.globalAlpha = dim ? 0.25 : 1;
        ctx.fill();
        ctx.lineWidth = 2;
        ctx.strokeStyle = "rgba(255,255,255,0.7)";
        ctx.stroke();
        ctx.globalAlpha = 1;
        // label
        ctx.font = "11px ui-sans-serif, system-ui, sans-serif";
        ctx.fillStyle = dim ? "rgba(148,163,184,0.5)" : "#e2e8f0";
        ctx.textAlign = "center";
        ctx.fillText(n.label, s.x, s.y + 26);
      }

      raf = requestAnimationFrame(draw);
    };

    const resize = () => {
      const parent = canvas.parentElement!;
      canvas.width = parent.clientWidth;
      canvas.height = parent.clientHeight;
    };
    resize();
    window.addEventListener("resize", resize);

    const onMove = (ev: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const id = pick(ev.clientX - rect.left, ev.clientY - rect.top);
      onHoverRef.current(id);
    };
    const onClick = (ev: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      const id = pick(ev.clientX - rect.left, ev.clientY - rect.top);
      onSelectRef.current(id);
    };
    canvas.addEventListener("mousemove", onMove);
    canvas.addEventListener("click", onClick);

    raf = requestAnimationFrame(draw);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("resize", resize);
      canvas.removeEventListener("mousemove", onMove);
      canvas.removeEventListener("click", onClick);
    };
  }, [nodes, edges, traffic]);

  return <canvas ref={canvasRef} className="w-full h-full block" />;
}
