"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { ExternalLink, Globe, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { deleteDeploymentAction } from "@/app/dashboard/actions";
import type { Deployment } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

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

  function handleRefresh() {
    startRefresh(() => {
      router.refresh();
    });
  }

  function handleDelete(deploymentId: string) {
    startTransition(async () => {
      const result = await deleteDeploymentAction(workspaceId, deploymentId);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success("Deployment deleted");
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

      {deployments.length === 0 ? (
        <div className="flex flex-col items-center gap-2 rounded-xl border py-12 text-center">
          <Globe className="size-6 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">
            No deployments yet. Deploy one with the REST or MCP API.
          </p>
        </div>
      ) : (
        <div className="divide-y rounded-xl border">
          {deployments.map((deployment) => (
            <div
              key={deployment.id}
              className="flex items-center justify-between gap-4 px-4 py-3"
            >
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
    </section>
  );
}
