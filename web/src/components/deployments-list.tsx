"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { ExternalLink, Globe, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import {
  bulkDeleteDeploymentsAction,
  deleteDeploymentAction,
} from "@/app/dashboard/actions";
import type { Deployment } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const CONTENT_TYPE_LABELS: Record<string, string> = {
  "text/html": "HTML",
  "text/markdown": "Markdown",
  "text/plain": "Text",
  "text/csv": "CSV",
  "application/json": "JSON",
  "image/svg+xml": "SVG",
  "image/png": "PNG",
  "image/jpeg": "JPEG",
  "image/gif": "GIF",
  "image/webp": "WebP",
  "application/pdf": "PDF",
};

function contentTypeLabel(contentType: string): string {
  return CONTENT_TYPE_LABELS[contentType] ?? contentType;
}

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

export function DeploymentsList({
  workspaceId,
  deployments,
}: {
  workspaceId: string;
  deployments: Deployment[];
}) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [refreshing, startRefresh] = useTransition();
  const [bulkPending, startBulkTransition] = useTransition();
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [confirmingBulk, setConfirmingBulk] = useState(false);

  const allSelected =
    deployments.length > 0 && selected.size === deployments.length;
  const someSelected = selected.size > 0 && !allSelected;

  function handleRefresh() {
    startRefresh(() => {
      router.refresh();
    });
  }

  function toggleAll(checked: boolean) {
    setSelected(checked ? new Set(deployments.map((d) => d.id)) : new Set());
  }

  function toggleOne(deploymentId: string, checked: boolean) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (checked) next.add(deploymentId);
      else next.delete(deploymentId);
      return next;
    });
  }

  function handleDelete(deploymentId: string) {
    startTransition(async () => {
      const result = await deleteDeploymentAction(workspaceId, deploymentId);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      setSelected((prev) => {
        if (!prev.has(deploymentId)) return prev;
        const next = new Set(prev);
        next.delete(deploymentId);
        return next;
      });
      toast.success("Deployment deleted");
      router.refresh();
    });
  }

  function handleBulkDelete() {
    startBulkTransition(async () => {
      const ids = Array.from(selected);
      const result = await bulkDeleteDeploymentsAction(workspaceId, ids);
      setConfirmingBulk(false);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      setSelected(new Set());
      const count = result.data.deletedIds.length;
      toast.success(count === 1 ? "Deployment deleted" : `${count} deployments deleted`);
      router.refresh();
    });
  }

  return (
    <section className="flex flex-col gap-4">
      <div className="flex items-center justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold">Deployments</h2>
          <p className="text-sm text-muted-foreground">
            Artifacts deployed to this workspace.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {selected.size > 0 && (
            <>
              <span className="text-sm text-muted-foreground">
                {selected.size} selected
              </span>
              <Button
                variant="destructive"
                size="sm"
                disabled={bulkPending}
                onClick={() => setConfirmingBulk(true)}
              >
                <Trash2 className="size-4" />
                Delete
              </Button>
            </>
          )}
          <Button
            variant="outline"
            size="sm"
            disabled={refreshing}
            onClick={handleRefresh}
          >
            <RefreshCw className={refreshing ? "size-4 animate-spin" : "size-4"} />
            Refresh
          </Button>
        </div>
      </div>

      {deployments.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border py-12 text-center">
          <Globe className="size-6 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No deployments yet. Deploy one with the REST or MCP API.
          </p>
        </div>
      ) : (
        <div className="divide-y rounded-xl border">
          <div className="flex items-center gap-3 px-4 py-2">
            <Checkbox
              checked={allSelected}
              indeterminate={someSelected}
              onCheckedChange={toggleAll}
              aria-label="Select all deployments"
            />
            <span className="text-xs text-muted-foreground">Select all</span>
          </div>
          {deployments.map((deployment) => (
            <div
              key={deployment.id}
              className="flex items-center justify-between gap-4 px-4 py-3"
            >
              <div className="flex min-w-0 items-center gap-3">
                <Checkbox
                  checked={selected.has(deployment.id)}
                  onCheckedChange={(checked) =>
                    toggleOne(deployment.id, checked === true)
                  }
                  aria-label={`Select ${deployment.slug}`}
                />
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <a
                      href={deployment.url}
                      target="_blank"
                      rel="noreferrer"
                      className="truncate font-mono text-sm hover:underline"
                    >
                      {deployment.slug}
                    </a>
                    <Badge variant="secondary">{contentTypeLabel(deployment.content_type)}</Badge>
                  </div>
                  <p className="text-xs text-muted-foreground">
                    created {formatDate(deployment.created_at)}
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  render={
                    <a href={deployment.url} target="_blank" rel="noreferrer" />
                  }
                >
                  <ExternalLink className="size-4" />
                  View
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  disabled={pending}
                  onClick={() => handleDelete(deployment.id)}
                >
                  <Trash2 className="size-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}

      <Dialog open={confirmingBulk} onOpenChange={setConfirmingBulk}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete {selected.size} deployment{selected.size === 1 ? "" : "s"}?</DialogTitle>
            <DialogDescription>
              This soft-deletes the selected deployments — their public URLs stop
              serving immediately. This can&apos;t be undone from the dashboard.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirmingBulk(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleBulkDelete}
              disabled={bulkPending}
            >
              <Trash2 className="size-4" />
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
