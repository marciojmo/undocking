import Link from "next/link";
import { notFound } from "next/navigation";
import { ChevronLeft } from "lucide-react";

import { ConnectionPanel } from "@/components/connection-panel";
import { DeploymentsList } from "@/components/deployments-list";
import { EditableSlug } from "@/components/editable-slug";
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
          Connected agents
        </Link>
        <EditableSlug workspaceId={workspace.id} initialSlug={workspace.slug} />
      </div>

      <ConnectionPanel workspaceId={workspace.id} keys={keys} />
      <DeploymentsList workspaceId={workspace.id} deployments={deployments} />
    </div>
  );
}
