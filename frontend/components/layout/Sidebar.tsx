"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";
import {
  LayoutDashboard,
  Server,
  Container,
  GitBranch,
  Play,
  FileText,
  FlaskConical,
  Trophy,
  CheckCircle,
  Medal,
  Eye,
  DollarSign,
  ChevronLeft,
  ChevronRight,
  Cpu,
} from "lucide-react";
import { NAV_ITEMS } from "@/lib/constants";
import { cn } from "@/lib/utils";

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  LayoutDashboard,
  Server,
  Container,
  GitBranch,
  Play,
  FileText,
  FlaskConical,
  Trophy,
  CheckCircle,
  Medal,
  Eye,
  DollarSign,
};

export function Sidebar() {
  const pathname = usePathname();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside
      className={cn(
        "h-screen border-r border-border bg-card/50 backdrop-blur-xl flex flex-col transition-all duration-300 sticky top-0",
        collapsed ? "w-16" : "w-60"
      )}
    >
      <div className="flex items-center gap-2 px-4 py-5 border-b border-border">
        <Cpu className="h-6 w-6 text-primary shrink-0" />
        {!collapsed && (
          <span className="font-bold text-lg tracking-tight">LLCP</span>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-1">
        {NAV_ITEMS.map((item) => {
          const Icon = ICON_MAP[item.icon];
          const isActive = pathname === item.href || pathname.startsWith(item.href + "/");

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "sidebar-item",
                isActive && "active",
                collapsed && "justify-center px-2"
              )}
              title={collapsed ? item.label : undefined}
            >
              {Icon && <Icon className="h-4 w-4 shrink-0" />}
              {!collapsed && <span>{item.label}</span>}
            </Link>
          );
        })}
      </nav>

      <button
        onClick={() => setCollapsed(!collapsed)}
        className="flex items-center justify-center p-3 border-t border-border hover:bg-muted transition-colors"
      >
        {collapsed ? (
          <ChevronRight className="h-4 w-4 text-muted-foreground" />
        ) : (
          <ChevronLeft className="h-4 w-4 text-muted-foreground" />
        )}
      </button>
    </aside>
  );
}
