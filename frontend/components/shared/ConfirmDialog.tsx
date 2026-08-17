"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { cn } from "@/lib/utils";

/**
 * Confirmation gate for destructive actions.
 *
 * Deleting a deployment tears down a running container and optionally its
 * downloaded weights — that was previously a single unguarded click.
 */
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  cancelLabel = "Cancel",
  destructive,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/55 backdrop-blur-[2px] data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <Dialog.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 w-[min(28rem,calc(100vw-2rem))]",
            "-translate-x-1/2 -translate-y-1/2",
            "surface-raised p-5 shadow-elev-3"
          )}
        >
          <Dialog.Title className="text-base font-semibold tracking-tight">{title}</Dialog.Title>
          {description && (
            <Dialog.Description className="text-sm text-muted-foreground mt-2 leading-relaxed">
              {description}
            </Dialog.Description>
          )}

          <div className="mt-5 flex justify-end gap-2">
            <Dialog.Close asChild>
              <button className="px-3.5 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:bg-surface-2 hover:text-foreground transition-colors">
                {cancelLabel}
              </button>
            </Dialog.Close>
            <button
              onClick={onConfirm}
              autoFocus
              className={cn(
                "px-3.5 py-2 rounded-md text-sm font-medium transition-colors",
                destructive
                  ? "bg-danger text-white hover:brightness-110"
                  : "bg-primary text-primary-foreground hover:bg-primary-hover"
              )}
            >
              {confirmLabel}
            </button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
