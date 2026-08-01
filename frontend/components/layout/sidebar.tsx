"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";
import {
  LayoutDashboard,
  Cloud,
  Server,
  GitBranch,
  FlaskConical,
  FileText,
  Beaker,
  BarChart3,
  Trophy,
  Activity,
  DollarSign,
  Settings,
  Search,
  Bell,
} from "lucide-react";

const navItems = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/providers", label: "Providers", icon: Cloud },
  { href: "/deployments", label: "Deployments", icon: Server },
  { href: "/routing", label: "Routing", icon: GitBranch },
  { href: "/playground", label: "Playground", icon: FlaskConical },
  { href: "/prompts", label: "Prompts", icon: FileText },
  { href: "/experiments", label: "Experiments", icon: Beaker },
  { href: "/benchmarks", label: "Benchmarks", icon: BarChart3 },
  { href: "/evaluations", label: "Evaluations", icon: Activity },
  { href: "/leaderboard", label: "Leaderboard", icon: Trophy },
  { href: "/observability", label: "Observability", icon: Activity },
  { href: "/cost", label: "Cost", icon: DollarSign },
];

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="fixed left-0 top-0 z-40 h-screen w-64 glass-strong border-r border-border/50 flex flex-col">
      <div className="flex items-center gap-2 px-6 py-5 border-b border-border/50">
        <div className="w-8 h-8 rounded-lg bg-primary/20 flex items-center justify-center">
          <Activity className="w-5 h-5 text-primary" />
        </div>
        <span className="font-bold text-lg tracking-tight">LLMPlane</span>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
        {navItems.map((item) => {
          const isActive = pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn("sidebar-item", isActive && "active")}
            >
              <item.icon className="w-4 h-4" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      <div className="px-3 py-4 border-t border-border/50">
        <Link href="/settings" className="sidebar-item">
          <Settings className="w-4 h-4" />
          <span>Settings</span>
        </Link>
      </div>
    </aside>
  );
}

export function Header() {
  return (
    <header className="sticky top-0 z-30 glass border-b border-border/50 px-6 py-3 flex items-center justify-between">
      <div className="flex items-center gap-4">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search... (Ctrl+K)"
            className="pl-9 pr-4 py-2 rounded-lg bg-background/50 border border-border/50 text-sm w-80 focus:outline-none focus:ring-2 focus:ring-primary/50"
          />
        </div>
      </div>
      <div className="flex items-center gap-4">
        <button className="relative p-2 rounded-lg hover:bg-accent transition-colors">
          <Bell className="w-5 h-5" />
          <span className="absolute top-1 right-1 w-2 h-2 bg-destructive rounded-full" />
        </button>
        <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center text-sm font-medium">
          A
        </div>
      </div>
    </header>
  );
}
