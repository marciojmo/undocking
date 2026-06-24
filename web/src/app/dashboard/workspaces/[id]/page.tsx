import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";

import { ApiKeysPanel } from "@/components/api-keys-panel";
import { DeploymentsList } from "@/components/deployments-list";
import { getWorkspace, listApiKeys, listDeployments } from "@/lib/api";

export default async function WorkspaceDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const workspace = await getWorkspace(id);
  if (!workspace) notFound();

  const [keys, deployments] = await Promise.all([
    listApiKeys(id),
    listDeployments(id),
  ]);

  return (
    <div className="flex flex-col gap-10">
      <div className="flex flex-col gap-2">
        <Link
          href="/dashboard"
          className="flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="size-4" />
          Workspaces
        </Link>
        <h1 className="text-2xl font-bold tracking-tight">{workspace.name}</h1>
        <p className="font-mono text-sm text-muted-foreground">
          /{workspace.slug}
        </p>
      </div>

      <ApiKeysPanel workspaceId={workspace.id} keys={keys} />
      <DeploymentsList workspaceId={workspace.id} deployments={deployments} />
    </div>
  );
}
