"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Search, LogOut, ChevronDown, Sun, Moon } from "lucide-react";
import { useTheme } from "next-themes";
import { API_BASE_URL } from "@/lib/constants";
import { openCommandPalette } from "@/components/layout/command-palette-bus";
import { cn } from "@/lib/utils";

interface UserData {
  id: string;
  email: string;
  name: string | null;
  avatar_url: string | null;
  provider: string;
}

export function Header() {
  const { resolvedTheme, setTheme } = useTheme();
  const router = useRouter();
  const [user, setUser] = useState<UserData | null>(null);
  const [showMenu, setShowMenu] = useState(false);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    const stored = localStorage.getItem("llcp_user");
    if (stored) {
      try {
        setUser(JSON.parse(stored));
      } catch {
        // Corrupt entry — treat as signed out rather than crashing the shell.
      }
    }
  }, []);

  async function handleLogout() {
    try {
      await fetch(`${API_BASE_URL}/auth/logout`, { method: "POST", credentials: "include" });
    } catch {
      // Sign out locally regardless — a failed round-trip must not strand the
      // user in a half-authenticated shell.
    }
    localStorage.removeItem("llcp_session_token");
    localStorage.removeItem("llcp_user");
    router.push("/");
  }

  const displayName = user?.name || user?.email?.split("@")[0] || "User";
  const initials = displayName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);

  return (
    <header className="h-14 shrink-0 sticky top-0 z-40 border-b border-border bg-background/85 backdrop-blur-xl flex items-center justify-between gap-4 px-5">
      {/*
       * A real button, not a readOnly input. The previous version synthesised a
       * fake ⌘K KeyboardEvent on click and hoped the palette's global listener
       * picked it up — which broke silently on any platform where the listener
       * checked ctrlKey instead.
       */}
      <button
        onClick={openCommandPalette}
        className="group flex items-center gap-2.5 w-full max-w-sm px-3 py-1.5 rounded-md border border-border bg-surface-1 text-sm text-subtle-foreground hover:border-border-strong hover:text-muted-foreground transition-colors"
      >
        <Search className="w-3.5 h-3.5 shrink-0" />
        <span className="flex-1 text-left">Search or jump to…</span>
        <kbd className="hidden sm:inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded border border-border bg-surface-2 font-mono text-[0.6875rem] text-subtle-foreground">
          ⌘K
        </kbd>
      </button>

      <div className="flex items-center gap-1">
        {/* Rendered only after mount: `resolvedTheme` is undefined on the server
            and would otherwise flash the wrong icon. */}
        {mounted && (
          <button
            onClick={() => setTheme(resolvedTheme === "dark" ? "light" : "dark")}
            aria-label={`Switch to ${resolvedTheme === "dark" ? "light" : "dark"} theme`}
            title={`Switch to ${resolvedTheme === "dark" ? "light" : "dark"} theme`}
            className="p-2 rounded-md text-muted-foreground hover:bg-surface-2 hover:text-foreground transition-colors"
          >
            {resolvedTheme === "dark" ? (
              <Sun className="w-4 h-4" />
            ) : (
              <Moon className="w-4 h-4" />
            )}
          </button>
        )}

        {/* The notification bell that used to sit here was removed: it rendered
            a permanent red unread dot with no data source behind it. */}

        <div className="relative">
          <button
            onClick={() => setShowMenu((s) => !s)}
            aria-haspopup="menu"
            aria-expanded={showMenu}
            className={cn(
              "flex items-center gap-2 pl-1 pr-2 py-1 rounded-md transition-colors",
              showMenu ? "bg-surface-2" : "hover:bg-surface-2"
            )}
          >
            {user?.avatar_url ? (
              // eslint-disable-next-line @next/next/no-img-element
              <img src={user.avatar_url} alt="" className="w-6 h-6 rounded-full" />
            ) : (
              <span className="grid place-items-center w-6 h-6 rounded-full bg-primary-subtle text-[0.6875rem] font-semibold text-primary">
                {initials}
              </span>
            )}
            <span className="text-sm font-medium hidden md:inline max-w-32 truncate">
              {displayName}
            </span>
            <ChevronDown className="w-3 h-3 text-subtle-foreground" />
          </button>

          {showMenu && (
            <>
              <div className="fixed inset-0 z-40" onClick={() => setShowMenu(false)} />
              <div
                role="menu"
                className="absolute right-0 top-full mt-1.5 w-60 z-50 surface-raised shadow-elev-3 overflow-hidden"
              >
                {user ? (
                  <div className="px-3.5 py-3 border-b border-border">
                    <p className="text-sm font-medium truncate">{user.name || user.email}</p>
                    <p className="text-xs text-muted-foreground truncate mt-0.5">{user.email}</p>
                    <p className="text-[0.6875rem] text-subtle-foreground mt-1.5">
                      signed in via {user.provider}
                    </p>
                  </div>
                ) : (
                  <div className="px-3.5 py-3 border-b border-border">
                    <p className="text-sm text-muted-foreground">Not signed in</p>
                  </div>
                )}
                <button
                  onClick={handleLogout}
                  role="menuitem"
                  className="w-full flex items-center gap-2.5 px-3.5 py-2.5 text-sm text-muted-foreground hover:bg-surface-2 hover:text-foreground transition-colors"
                >
                  <LogOut className="w-4 h-4" />
                  Sign out
                </button>
              </div>
            </>
          )}
        </div>
      </div>
    </header>
  );
}
