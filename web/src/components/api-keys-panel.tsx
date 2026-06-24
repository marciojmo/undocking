"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Check, Copy, KeyRound, Plus } from "lucide-react";
import { toast } from "sonner";

import { issueKeyAction, revokeKeyAction } from "@/app/dashboard/actions";
import type { ApiKey } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
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
  const [pending, startTransition] = useTransition();

  function openDialog() {
    setName("");
    setRevealed(null);
    setCopied(false);
    setDialogOpen(true);
  }

  function handleDialogChange(open: boolean) {
    setDialogOpen(open);
    if (!open && revealed) router.refresh();
  }

  function handleCreate() {
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
    startTransition(async () => {
      const result = await revokeKeyAction(workspaceId, keyId);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success("Key revoked");
      router.refresh();
    });
  }

  async function copyKey() {
    if (!revealed) return;
    await navigator.clipboard.writeText(revealed);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
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

      {keys.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border py-12 text-center">
          <KeyRound className="size-6 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">No API keys yet.</p>
        </div>
      ) : (
        <div className="divide-y rounded-xl border">
          {keys.map((key) => {
            const revoked = key.revoked_at !== null;
            return (
              <div
                key={key.id}
                className="flex items-center justify-between gap-4 px-4 py-3"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="truncate font-medium">{key.name}</p>
                    {revoked && <Badge variant="secondary">Revoked</Badge>}
                  </div>
                  <p className="font-mono text-xs text-muted-foreground">
                    {key.key_prefix}… · created {formatDate(key.created_at)}
                  </p>
                </div>
                {!revoked && (
                  <Button
                    variant="ghost"
                    size="sm"
                    disabled={pending}
                    onClick={() => handleRevoke(key.id)}
                  >
                    Revoke
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={handleDialogChange}>
        <DialogContent>
          {revealed ? (
            <>
              <DialogHeader>
                <DialogTitle>Copy your API key</DialogTitle>
                <DialogDescription>
                  This is the only time the key is shown. Store it somewhere safe.
                </DialogDescription>
              </DialogHeader>
              <div className="flex items-center gap-2">
                <code className="flex-1 truncate rounded-md border bg-muted px-3 py-2 font-mono text-sm">
                  {revealed}
                </code>
                <Button variant="outline" size="icon" onClick={copyKey}>
                  {copied ? <Check className="size-4" /> : <Copy className="size-4" />}
                </Button>
              </div>
              <DialogFooter>
                <Button onClick={() => handleDialogChange(false)}>Done</Button>
              </DialogFooter>
            </>
          ) : (
            <>
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
                />
              </div>
              <DialogFooter>
                <Button
                  onClick={handleCreate}
                  disabled={pending || !name.trim()}
                >
                  Create key
                </Button>
              </DialogFooter>
            </>
          )}
        </DialogContent>
      </Dialog>
    </section>
  );
}
