"use client";

import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { CameraMode } from "@/components/command-center/types";

interface CommandCenterUIState {
  viewMode: "3d" | "2d";
  reduceMotion: boolean;
  cameraMode: CameraMode;
  setViewMode: (m: "3d" | "2d") => void;
  setReduceMotion: (v: boolean) => void;
  setCameraMode: (m: CameraMode) => void;
}

/**
 * UI state for the Command Center (PRD §31: UI state lives in its own store,
 * separate from server/real-time state). Persisted so a user's preferences for
 * 2D fallback / reduced motion survive reloads.
 */
export const useCommandCenterUI = create<CommandCenterUIState>()(
  persist(
    (set) => ({
      viewMode: "3d",
      reduceMotion: false,
      cameraMode: "overview",
      setViewMode: (viewMode) => set({ viewMode }),
      setReduceMotion: (reduceMotion) => set({ reduceMotion }),
      setCameraMode: (cameraMode) => set({ cameraMode }),
    }),
    { name: "llcp-command-center-ui" }
  )
);
