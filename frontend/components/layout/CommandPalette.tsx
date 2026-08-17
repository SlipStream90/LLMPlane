"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Command } from "cmdk";
import { ExternalLink } from "lucide-react";
import { NAV_ITEMS } from "@/lib/constants";
import { NAV_ICONS as ICON_MAP } from "@/lib/nav-icons";
import { onOpenCommandPalette } from "@/components/layout/command-palette-bus";

const GRAFANA_URL = process.env.NEXT_PUBLIC_GRAFANA_URL || "http://localhost:3001";
const LANGFUSE_URL = process.env.NEXT_PUBLIC_LANGFUSE_URL || "https://cloud.langfuse.com";

export function CommandPalette() {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setOpen((o) => !o);
      }
    }
    document.addEventListener("keydown", onKeyDown);
    // Also openable from the header's search button, without it having to
    // synthesise a keyboard event.
    const offBus = onOpenCommandPalette(() => setOpen(true));
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      offBus();
    };
  }, []);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]">
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm" onClick={() => setOpen(false)} />
      <Command className="relative w-full max-w-lg surface-raised rounded-lg overflow-hidden shadow-2xl">
        <Command.Input
          placeholder="Type a command or search..."
          className="w-full px-4 py-3 bg-transparent border-b border-border text-sm focus:outline-none"
        />
        <Command.List className="max-h-80 overflow-y-auto p-2">
          <Command.Empty className="py-6 text-center text-muted-foreground text-sm">
            No results found.
          </Command.Empty>

          <Command.Group heading="Navigation">
            {NAV_ITEMS.map((item) => {
              const Icon = ICON_MAP[item.icon];
              return (
                <Command.Item
                  key={item.href}
                  value={item.label}
                  onSelect={() => {
                    router.push(item.href);
                    setOpen(false);
                  }}
                  className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm cursor-pointer hover:bg-muted transition-colors"
                >
                  {Icon && <Icon className="h-4 w-4 text-muted-foreground" />}
                  <span>{item.label}</span>
                </Command.Item>
              );
            })}
          </Command.Group>

          <Command.Separator className="my-2 h-px bg-border" />

          <Command.Group heading="External Links">
            <Command.Item
              value="Grafana"
              onSelect={() => {
                window.open(GRAFANA_URL, "_blank");
                setOpen(false);
              }}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm cursor-pointer hover:bg-muted transition-colors"
            >
              <ExternalLink className="h-4 w-4 text-muted-foreground" />
              <span>Grafana Dashboard</span>
            </Command.Item>
            <Command.Item
              value="Langfuse"
              onSelect={() => {
                window.open(LANGFUSE_URL, "_blank");
                setOpen(false);
              }}
              className="flex items-center gap-3 px-3 py-2 rounded-lg text-sm cursor-pointer hover:bg-muted transition-colors"
            >
              <ExternalLink className="h-4 w-4 text-muted-foreground" />
              <span>Langfuse Cloud</span>
            </Command.Item>
          </Command.Group>
        </Command.List>
      </Command>
    </div>
  );
}
