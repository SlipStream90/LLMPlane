/**
 * Tiny event bus for opening the command palette from anywhere.
 *
 * The header used to synthesise a fake ⌘K `KeyboardEvent` and dispatch it at
 * `document`, relying on the palette's global hotkey listener to catch it. That
 * coupled the button to the exact modifier the listener happened to check, and
 * failed silently when they disagreed.
 */
const OPEN_EVENT = "llcp:open-command-palette";

export function openCommandPalette(): void {
  document.dispatchEvent(new CustomEvent(OPEN_EVENT));
}

export function onOpenCommandPalette(handler: () => void): () => void {
  document.addEventListener(OPEN_EVENT, handler);
  return () => document.removeEventListener(OPEN_EVENT, handler);
}
