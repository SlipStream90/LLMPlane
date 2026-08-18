"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { API_BASE_URL } from "@/lib/api";
import { cn } from "@/lib/utils";
import { KeyRound, Sparkles, Loader2, Copy, Check, AlertTriangle } from "lucide-react";

type Mode = "key" | "bootstrap";

/**
 * Sign-in.
 *
 * The API-key path exists because it is the only one that works without OAuth
 * credentials configured on the backend. Previously this screen offered "Or use
 * an API key directly", which merely routed to /dashboard without collecting or
 * storing anything — so the app landed unauthenticated and every request 401'd.
 * `llcp_api_key` was read in two places and written in none.
 */
export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>("key");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [apiKey, setApiKey] = useState("");
  const [bootstrapToken, setBootstrapToken] = useState("");
  const [mintedKey, setMintedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (localStorage.getItem("llcp_session_token") || localStorage.getItem("llcp_api_key")) {
      router.replace("/dashboard");
    }
  }, [router]);

  /** Verify a key against a cheap authenticated endpoint before persisting it. */
  async function verifyAndStore(key: string): Promise<boolean> {
    const res = await fetch(`${API_BASE_URL}/providers`, {
      headers: { Authorization: `Bearer ${key}` },
    });
    if (res.status === 401 || res.status === 403) {
      setError("That API key was rejected by the backend.");
      return false;
    }
    if (!res.ok) {
      setError(
        `The backend answered ${res.status} for /providers. If this is a 404, ` +
          `NEXT_PUBLIC_API_URL is pointing at the wrong path.`
      );
      return false;
    }
    localStorage.setItem("llcp_api_key", key);
    return true;
  }

  async function submitKey(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (await verifyAndStore(apiKey.trim())) router.replace("/dashboard");
    } catch {
      setError("Could not reach the backend. Check NEXT_PUBLIC_API_URL and CORS.");
    } finally {
      setBusy(false);
    }
  }

  async function submitBootstrap(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`${API_BASE_URL}/auth/bootstrap-key`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-Bootstrap-Token": bootstrapToken.trim(),
        },
        body: JSON.stringify({}),
      });
      const body = await res.json().catch(() => null);

      if (!res.ok) {
        // 409 means a key already exists — the endpoint refuses to mint a second
        // one unless explicitly asked, to avoid silently proliferating admin keys.
        setError(
          body?.detail ??
            (res.status === 401
              ? "That bootstrap token was rejected."
              : `Bootstrap failed (${res.status}).`)
        );
        return;
      }

      const key: string | undefined = body?.api_key?.key;
      if (!key) {
        setError("The backend did not return a key.");
        return;
      }
      localStorage.setItem("llcp_api_key", key);
      setMintedKey(key);
    } catch {
      setError("Could not reach the backend. Check NEXT_PUBLIC_API_URL and CORS.");
    } finally {
      setBusy(false);
    }
  }

  function oauth(provider: "github" | "google") {
    window.location.href = `${API_BASE_URL}/auth/oauth/${provider}/login`;
  }

  if (mintedKey) {
    return (
      <main className="min-h-screen grid place-items-center px-6 grid-bg">
        <div className="surface max-w-md w-full p-6">
          <h1 className="text-lg font-semibold tracking-tight">Your admin API key</h1>
          <p className="text-sm text-muted-foreground mt-2">
            Copy it now — the backend stores only a hash and cannot show it again. It has
            been saved to this browser, so you are already signed in.
          </p>
          <div className="mt-4 flex items-center gap-2">
            <code className="flex-1 px-3 py-2 rounded-md bg-surface-2 border border-border font-mono text-xs break-all">
              {mintedKey}
            </code>
            <button
              onClick={() => {
                navigator.clipboard?.writeText(mintedKey);
                setCopied(true);
              }}
              aria-label="Copy API key"
              className="p-2 rounded-md border border-border text-muted-foreground hover:text-foreground hover:bg-surface-2 transition-colors"
            >
              {copied ? <Check className="w-4 h-4 text-success" /> : <Copy className="w-4 h-4" />}
            </button>
          </div>
          <button
            onClick={() => router.replace("/dashboard")}
            className="w-full mt-5 px-4 py-2.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary-hover transition-colors"
          >
            Continue to dashboard
          </button>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen grid place-items-center px-6 grid-bg">
      <div className="w-full max-w-md">
        <div className="text-center mb-7">
          <span className="grid place-items-center w-12 h-12 mx-auto rounded-xl bg-primary text-primary-foreground">
            <Sparkles className="w-6 h-6" />
          </span>
          <h1 className="text-xl font-semibold tracking-tight mt-4">LLMPlane</h1>
          <p className="text-sm text-muted-foreground mt-1.5">
            Sign in to manage your LLM infrastructure
          </p>
        </div>

        <div className="surface p-5">
          <div className="flex gap-1 p-1 rounded-md bg-surface-2 mb-5">
            {(
              [
                ["key", "I have an API key"],
                ["bootstrap", "First-time setup"],
              ] as const
            ).map(([m, label]) => (
              <button
                key={m}
                onClick={() => {
                  setMode(m);
                  setError(null);
                }}
                className={cn(
                  "flex-1 px-3 py-1.5 rounded text-sm font-medium transition-colors",
                  mode === m
                    ? "bg-surface-1 text-foreground shadow-elev-1"
                    : "text-muted-foreground hover:text-foreground"
                )}
              >
                {label}
              </button>
            ))}
          </div>

          {error && (
            <div className="mb-4 flex items-start gap-2 p-3 rounded-md bg-danger-subtle border border-danger/25">
              <AlertTriangle className="w-4 h-4 text-danger shrink-0 mt-0.5" />
              <p className="text-sm text-danger break-words">{error}</p>
            </div>
          )}

          {mode === "key" ? (
            <form onSubmit={submitKey} className="space-y-3">
              <label className="block">
                <span className="text-sm font-medium">Project API key</span>
                <input
                  type="password"
                  autoComplete="off"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="llcp_..."
                  className="mt-1.5 w-full px-3 py-2 rounded-md bg-surface-2 border border-border font-mono text-sm focus:outline-none focus:border-primary"
                />
              </label>
              <p className="text-xs text-subtle-foreground">
                Stored in this browser only, and sent as a bearer token.
              </p>
              <button
                type="submit"
                disabled={busy || !apiKey.trim()}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary-hover transition-colors disabled:opacity-50 disabled:pointer-events-none"
              >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <KeyRound className="w-4 h-4" />}
                Sign in
              </button>
            </form>
          ) : (
            <form onSubmit={submitBootstrap} className="space-y-3">
              <label className="block">
                <span className="text-sm font-medium">Bootstrap token</span>
                <input
                  type="password"
                  autoComplete="off"
                  value={bootstrapToken}
                  onChange={(e) => setBootstrapToken(e.target.value)}
                  placeholder="BOOTSTRAP_ADMIN_TOKEN"
                  className="mt-1.5 w-full px-3 py-2 rounded-md bg-surface-2 border border-border font-mono text-sm focus:outline-none focus:border-primary"
                />
              </label>
              <p className="text-xs text-subtle-foreground">
                The value of <span className="font-mono">BOOTSTRAP_ADMIN_TOKEN</span> in your
                backend environment. This creates the default project and one admin API key.
              </p>
              <button
                type="submit"
                disabled={busy || !bootstrapToken.trim()}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-md bg-primary text-primary-foreground text-sm font-medium hover:bg-primary-hover transition-colors disabled:opacity-50 disabled:pointer-events-none"
              >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                Create my first API key
              </button>
            </form>
          )}

          <div className="mt-5 pt-5 border-t border-border">
            <p className="text-xs text-subtle-foreground text-center mb-3">
              Or continue with OAuth (requires provider credentials on the backend)
            </p>
            <div className="grid grid-cols-2 gap-2">
              <button
                onClick={() => oauth("github")}
                className="px-3 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:bg-surface-2 hover:text-foreground transition-colors"
              >
                GitHub
              </button>
              <button
                onClick={() => oauth("google")}
                className="px-3 py-2 rounded-md border border-border text-sm font-medium text-muted-foreground hover:bg-surface-2 hover:text-foreground transition-colors"
              >
                Google
              </button>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
