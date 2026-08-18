"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";
import { CommandPalette } from "@/components/layout/CommandPalette";
import { WebSocketProvider } from "@/components/shared/WebSocketProvider";

/**
 * Authenticated shell.
 *
 * Bounces to the sign-in screen when the browser holds no credential at all.
 * Without this, an unauthenticated visitor landed here and every page rendered
 * its own 401 error card, which reads as "the whole app is broken" rather than
 * "you are not signed in".
 *
 * This is a UX redirect, not a security boundary — the backend authenticates
 * every request regardless.
 */
export default function AppLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const [checked, setChecked] = useState(false);

  useEffect(() => {
    const authed =
      !!localStorage.getItem("llcp_api_key") || !!localStorage.getItem("llcp_session_token");
    if (!authed) {
      router.replace("/");
      return;
    }
    setChecked(true);
  }, [router]);

  // Render nothing until the check completes, so the shell does not flash
  // before a redirect.
  if (!checked) return null;

  return (
    <WebSocketProvider>
      <div className="min-h-screen flex">
        <Sidebar />
        <div className="flex-1 flex flex-col min-w-0">
          <Header />
          <main className="flex-1 overflow-auto">{children}</main>
        </div>
      </div>
      <CommandPalette />
    </WebSocketProvider>
  );
}
