"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Check, Copy, KeyRound, RefreshCw } from "lucide-react";
import { toast } from "sonner";

import { renewKeyAction } from "@/app/dashboard/actions";
import type { ApiKey } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

function formatDate(value: string): string {
  // Pinned to en-US: this renders in a Server Component's client twin, so an
  // unpinned locale (server default vs. the browser's) causes a hydration
  // mismatch whenever they differ.
  return new Date(value).toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/**
 * Public origin of the FastAPI backend (no trailing slash). Agents must talk
 * to the API directly — never through this dashboard's /api proxy — so the
 * web origin is deliberately not a fallback here.
 */
function apiOrigin(): string {
  const override = process.env.NEXT_PUBLIC_API_URL;
  if (override) return override.replace(/\/$/, "");
  return "http://localhost:8000";
}

/** Resolves the public MCP endpoint, preferring an explicit override. */
function mcpUrl(): string {
  const override = process.env.NEXT_PUBLIC_MCP_URL;
  if (override) return override;
  return `${apiOrigin()}/mcp`;
}

/** Builds a paste-ready setup prompt for an LLM agent. */
function llmPrompt(key: string): string {
  const api = apiOrigin();
  const config = JSON.stringify(
    {
      mcpServers: {
        undocking: {
          type: "http",
          url: mcpUrl(),
          headers: { Authorization: `Bearer ${key}` },
        },
      },
    },
    null,
    2,
  );
  return `Set up Undocking for me. Undocking publishes LLM-generated artifacts (HTML, Markdown, images, PDFs, JSON, SVG, and more) to public URLs via MCP or REST. Both are served directly by the Undocking API at ${api} — always call that origin directly, never a dashboard/web URL. API base: ${api}/v1

1. Add this MCP server to my configuration. Merge with existing \`mcpServers\` — do not remove other servers:

${config}

2. Reload the MCP connection so the \`undocking\` server is active.

3. Verify: call \`list_deployments\` on the \`undocking\` MCP server. Expect \`{"deployments": [...]}\`. If MCP is unavailable, run:
   curl -s ${api}/v1/deployments -H "Authorization: Bearer ${key}"

4. Publish a demo artifact using \`deploy_artifact\` with content_type "text/markdown" and content "# You're live on Undocking!". Report the public URL.

From now on, use the \`undocking\` MCP server whenever I ask to publish, undock, deploy, or share an artifact.

Auth for all REST calls: \`Authorization: Bearer ${key}\`
Full guide (content types, presigned uploads, etc.): GET ${api}/v1/instructions`;
}

export function ConnectionPanel({
  workspaceId,
  keys,
}: {
  workspaceId: string;
  keys: ApiKey[];
}) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [revealedKey, setRevealedKey] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [promptCopied, setPromptCopied] = useState(false);
  const [pending, startTransition] = useTransition();

  const activeKey = keys.find((key) => key.revoked_at === null) ?? null;
  const dialogOpen = confirming || revealedKey !== null;

  useEffect(() => {
    const storageKey = `pending-key:${workspaceId}`;
    const pendingKey = sessionStorage.getItem(storageKey);
    if (pendingKey) {
      sessionStorage.removeItem(storageKey);
      // sessionStorage isn't available during SSR, so this can only be read
      // post-mount — that read-then-setState is exactly what this effect syncs.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setRevealedKey(pendingKey);
    }
    // Only ever run once per mount — the popup should only auto-open right
    // after the redirect from "Connect a new agent".
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function handleDialogChange(open: boolean) {
    if (!open) {
      const wasRevealed = revealedKey !== null;
      setConfirming(false);
      setRevealedKey(null);
      setCopied(false);
      setPromptCopied(false);
      if (wasRevealed) router.refresh();
    }
  }

  function handleRenew() {
    startTransition(async () => {
      const result = await renewKeyAction(workspaceId);
      if (!result.ok) {
        toast.error(result.error);
        setConfirming(false);
        return;
      }
      setConfirming(false);
      setRevealedKey(result.data.key);
    });
  }

  async function copyKey() {
    if (!revealedKey) return;
    await navigator.clipboard.writeText(revealedKey);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  async function copyPrompt() {
    if (!revealedKey) return;
    await navigator.clipboard.writeText(llmPrompt(revealedKey));
    setPromptCopied(true);
    setTimeout(() => setPromptCopied(false), 1500);
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">Connection</h2>
          <p className="text-sm text-muted-foreground">
            {activeKey
              ? `Connected · created ${formatDate(activeKey.created_at)}`
              : "No active connection."}
          </p>
        </div>
        <Button size="sm" onClick={() => setConfirming(true)}>
          <RefreshCw className="size-4" />
          Renew Connection
        </Button>
      </div>

      <Dialog open={dialogOpen} onOpenChange={handleDialogChange}>
        <DialogContent className="sm:max-w-2xl">
          {revealedKey ? (
            <>
              <DialogHeader>
                <DialogTitle>Copy your API key</DialogTitle>
                <DialogDescription>
                  This is the only time the key is shown. Store it somewhere safe.
                </DialogDescription>
              </DialogHeader>
              <div className="flex items-center gap-2">
                <code className="block flex-1 truncate rounded-md border bg-muted px-3 py-2 font-mono text-sm">
                  {revealedKey}
                </code>
                <Button variant="outline" size="icon" onClick={copyKey}>
                  {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
                </Button>
              </div>
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium">Agent prompt</p>
                  <Button variant="outline" size="sm" onClick={copyPrompt}>
                    {promptCopied ? (
                      <Check className="size-4" />
                    ) : (
                      <Copy className="size-4" />
                    )}
                    Copy LLM Prompt
                  </Button>
                </div>
                <p className="text-sm text-muted-foreground">
                  Paste into your agent — it should create the MCP config and
                  verify the connection.
                </p>
                <pre className="max-h-56 overflow-auto rounded-md border bg-muted px-3 py-2 font-mono text-xs whitespace-pre-wrap">
                  {llmPrompt(revealedKey)}
                </pre>
              </div>
              <DialogFooter>
                <Button onClick={() => handleDialogChange(false)}>Done</Button>
              </DialogFooter>
            </>
          ) : (
            <>
              <DialogHeader>
                <DialogTitle>Renew connection?</DialogTitle>
                <DialogDescription>
                  This immediately invalidates the current key. Any agent still
                  using it will stop working until it&apos;s reconnected with the
                  new key.
                </DialogDescription>
              </DialogHeader>
              <DialogFooter>
                <Button variant="outline" onClick={() => setConfirming(false)}>
                  Cancel
                </Button>
                <Button onClick={handleRenew} disabled={pending}>
                  <KeyRound className="size-4" />
                  Renew Connection
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
}
