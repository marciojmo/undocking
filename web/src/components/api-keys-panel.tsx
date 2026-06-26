"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Check, Copy, KeyRound, Plus } from "lucide-react";
import { toast } from "sonner";

import { issueKeyAction, revokeKeyAction } from "@/app/dashboard/actions";
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
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** Resolves the public MCP endpoint, preferring an explicit override. */
function mcpUrl(): string {
  const override = process.env.NEXT_PUBLIC_MCP_URL;
  if (override) return override;
  if (typeof window !== "undefined") {
    return `${window.location.origin}/api/mcp`;
  }
  return "/api/mcp";
}

/** Resolves the public REST API base (no trailing slash). Override with NEXT_PUBLIC_API_URL. */
function apiBaseUrl(): string {
  const override = process.env.NEXT_PUBLIC_API_URL;
  if (override) return override.replace(/\/$/, "");
  const mcpOverride = process.env.NEXT_PUBLIC_MCP_URL;
  if (mcpOverride) return mcpOverride.replace(/\/mcp\/?$/, "");
  if (typeof window !== "undefined") {
    return `${window.location.origin}/api`;
  }
  return "/api";
}

/** Builds a paste-ready MCP server config for the given key. */
function mcpConfig(key: string): string {
  return JSON.stringify(
    {
      mcpServers: {
        ship: {
          type: "http",
          url: mcpUrl(),
          headers: { Authorization: `Bearer ${key}` },
        },
      },
    },
    null,
    2,
  );
}

/** Builds a paste-ready setup prompt for an LLM agent. */
function llmPrompt(key: string): string {
  const api = apiBaseUrl();
  const config = mcpConfig(key);
  return `Set up Ship for me. Ship publishes HTML or Markdown artifacts to public URLs via MCP or REST. API base: ${api}/v1

1. Add this Streamable HTTP MCP server to my agent's MCP configuration. Merge with any existing \`mcpServers\` entries — do not remove other servers:

${config}

2. Restart or reload the MCP connection so the \`ship\` server is active.

3. Verify Ship is connected. Read the \`how_to_deploy\` prompt from the \`ship\` MCP server, or run:
   curl -s ${api}/v1/deployments -H "Authorization: Bearer ${key}"
   Expect JSON with a \`deployments\` array (empty is fine).

4. Demo that it works: use the \`deploy_artifact\` MCP tool (or POST ${api}/v1/deployments) to publish a one-line Markdown page with content "# You're ready to Ship!" and content_type "markdown". Tell me the public URL and open it when done.

Use \`Authorization: Bearer ${key}\` on all REST requests. Full deployment guide: GET ${api}/v1/instructions`;
}

export function ApiKeysPanel({
  workspaceId,
  keys,
}: {
  workspaceId: string;
  keys: ApiKey[];
}) {
  const router = useRouter();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [name, setName] = useState("");
  const [revealed, setRevealed] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [promptCopied, setPromptCopied] = useState(false);
  const [configCopied, setConfigCopied] = useState(false);
  const [removingId, setRemovingId] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const activeKeys = keys.filter((key) => key.revoked_at === null);

  function openDialog() {
    setName("");
    setRevealed(null);
    setCopied(false);
    setPromptCopied(false);
    setConfigCopied(false);
    setDialogOpen(true);
  }

  function handleDialogChange(open: boolean) {
    setDialogOpen(open);
    if (!open && revealed) router.refresh();
  }

  function handleCreate(event: React.FormEvent) {
    event.preventDefault();
    if (!name.trim()) return;
    startTransition(async () => {
      const result = await issueKeyAction(workspaceId, name);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      setRevealed(result.data.key);
    });
  }

  function handleRevoke(keyId: string) {
    // Fade the row out first, then revoke and refresh once the transition ends.
    setRemovingId(keyId);
    setTimeout(() => {
      startTransition(async () => {
        const result = await revokeKeyAction(workspaceId, keyId);
        if (!result.ok) {
          setRemovingId(null);
          toast.error(result.error);
          return;
        }
        toast.success("Key revoked");
        router.refresh();
        setRemovingId(null);
      });
    }, 300);
  }

  async function copyKey() {
    if (!revealed) return;
    await navigator.clipboard.writeText(revealed);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }

  async function copyPrompt() {
    if (!revealed) return;
    await navigator.clipboard.writeText(llmPrompt(revealed));
    setPromptCopied(true);
    setTimeout(() => setPromptCopied(false), 1500);
  }

  async function copyConfig() {
    if (!revealed) return;
    await navigator.clipboard.writeText(mcpConfig(revealed));
    setConfigCopied(true);
    setTimeout(() => setConfigCopied(false), 1500);
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold">API keys</h2>
          <p className="text-sm text-muted-foreground">
            Bearer tokens for the REST and MCP APIs. Shown once at creation.
          </p>
        </div>
        <Button size="sm" onClick={openDialog}>
          <Plus className="size-4" />
          Create key
        </Button>
      </div>

      {activeKeys.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border py-12 text-center">
          <KeyRound className="size-6 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">No API keys yet.</p>
        </div>
      ) : (
        <div className="divide-y rounded-xl border">
          {activeKeys.map((key) => {
            const removing = removingId === key.id;
            return (
              <div
                key={key.id}
                className={`flex items-center justify-between gap-4 overflow-hidden px-4 py-3 transition-all duration-300 ${removing ? "max-h-0 py-0 opacity-0" : "max-h-24 opacity-100"
                  }`}
              >
                <div className="min-w-0">
                  <p className="truncate font-medium">{key.name}</p>
                  <p className="font-mono text-xs text-muted-foreground">
                    {key.key_prefix}… · created {formatDate(key.created_at)}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  disabled={pending || removing}
                  onClick={() => handleRevoke(key.id)}
                >
                  Revoke
                </Button>
              </div>
            );
          })}
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={handleDialogChange}>
        <DialogContent className="sm:max-w-3xl">
          {revealed ? (
            <>
              <DialogHeader>
                <DialogTitle>Copy your API key</DialogTitle>
                <DialogDescription>
                  This is the only time the key is shown. Store it somewhere safe.
                </DialogDescription>
              </DialogHeader>
              <div className="flex items-center gap-2">
                <code className="block flex-1 truncate rounded-md border bg-muted px-3 py-2 font-mono text-sm">
                  {revealed}
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
                  {llmPrompt(revealed)}
                </pre>
              </div>
              <div className="flex flex-col gap-2">
                <div className="flex items-center justify-between gap-2">
                  <p className="text-sm font-medium">MCP config</p>
                  <Button variant="outline" size="sm" onClick={copyConfig}>
                    {configCopied ? (
                      <Check className="size-4" />
                    ) : (
                      <Copy className="size-4" />
                    )}
                    Copy config
                  </Button>
                </div>
                <p className="text-sm text-muted-foreground">
                  Paste into your MCP client&apos;s configuration, then reload.
                </p>
                <pre className="max-h-48 overflow-auto rounded-md border bg-muted px-3 py-2 font-mono text-xs">
                  {mcpConfig(revealed)}
                </pre>
              </div>
              <DialogFooter>
                <Button onClick={() => handleDialogChange(false)}>Done</Button>
              </DialogFooter>
            </>
          ) : (
            <form onSubmit={handleCreate} className="grid gap-4">
              <DialogHeader>
                <DialogTitle>Create API key</DialogTitle>
                <DialogDescription>
                  Give the key a name so you can recognize it later.
                </DialogDescription>
              </DialogHeader>
              <div className="flex flex-col gap-2">
                <Label htmlFor="key-name">Name</Label>
                <Input
                  id="key-name"
                  value={name}
                  onChange={(event) => setName(event.target.value)}
                  placeholder="e.g. production, ci, my-agent"
                  maxLength={64}
                  autoFocus
                />
              </div>
              <DialogFooter>
                <Button type="submit" disabled={pending || !name.trim()}>
                  Create key
                </Button>
              </DialogFooter>
            </form>
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
}
