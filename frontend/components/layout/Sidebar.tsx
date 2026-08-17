"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { PanelLeftClose, PanelLeftOpen, Cpu } from "lucide-react";
import { NAV_ITEMS, NAV_GROUP_ORDER } from "@/lib/constants";
import { NAV_ICONS } from "@/lib/nav-icons";
import { cn } from "@/lib/utils";

const COLLAPSE_KEY = "llcp_sidebar_collapsed";

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);
  const [hydrated, setHydrated] = useState(false);

  // Collapse state was local-only, so it reset on every navigation that
  // remounted the shell. Persisted, but read after mount to avoid a hydration
  // mismatch between the server render and localStorage.
  useEffect(() => {
    setCollapsed(localStorage.getItem(COLLAPSE_KEY) === "1");
    setHydrated(true);
  }, []);

  function toggle() {
    setCollapsed((c) => {
      const next = !c;
      localStorage.setItem(COLLAPSE_KEY, next ? "1" : "0");
      return next;
    });
  }

  return (
    <aside
      className={cn(
        "h-screen sticky top-0 z-30 shrink-0 flex flex-col",
        "border-r border-border bg-background-subtle",
        hydrated && "transition-[width] duration-200 ease-out",
        collapsed ? "w-[3.75rem]" : "w-[15rem]"
      )}
    >
      <div className="flex items-center gap-2.5 h-14 px-4 border-b border-border">
        <span className="grid place-items-center w-7 h-7 rounded-md bg-primary text-primary-foreground shrink-0">
          <Cpu className="w-4 h-4" />
        </span>
        {!collapsed && (
          <span className="font-semibold tracking-tight truncate">LLMPlane</span>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto py-3 px-2">
        {NAV_GROUP_ORDER.map((group) => {
          const items = NAV_ITEMS.filter((i) => i.group === group);
          if (!items.length) return null;

          return (
            <div key={group} className="mb-4 last:mb-0">
              {!collapsed && (
                <p className="px-3 mb-1 text-[0.6875rem] font-medium uppercase tracking-wider text-subtle-foreground">
                  {group}
                </p>
              )}
              {collapsed && <div className="mx-2 mb-2 border-t border-border" />}

              <div className="space-y-0.5">
                {items.map((item) => {
                  const Icon = NAV_ICONS[item.icon];
                  const active =
                    pathname === item.href || pathname.startsWith(item.href + "/");

                  return (
                    <Link
                      key={item.href}
                      href={item.href}
                      data-active={active}
                      aria-current={active ? "page" : undefined}
                      title={collapsed ? item.label : undefined}
                      className={cn("nav-item relative", collapsed && "justify-center px-0")}
                    >
                      {active && (
                        <span className="absolute left-0 top-1/2 -translate-y-1/2 h-4 w-0.5 rounded-r bg-primary" />
                      )}
                      {Icon && <Icon className="w-4 h-4 shrink-0" />}
                      {!collapsed && <span className="truncate">{item.label}</span>}
                    </Link>
                  );
                })}
              </div>
            </div>
          );
        })}
      </nav>

      <button
        onClick={toggle}
        aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
        className="flex items-center gap-2.5 px-4 py-3 border-t border-border text-muted-foreground hover:text-foreground hover:bg-surface-2 transition-colors"
      >
        {collapsed ? (
          <PanelLeftOpen className="w-4 h-4 mx-auto" />
        ) : (
          <>
            <PanelLeftClose className="w-4 h-4" />
            <span className="text-sm">Collapse</span>
          </>
        )}
      </button>
    </aside>
  );
}
