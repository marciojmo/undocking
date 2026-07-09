import Link from "next/link";
import { ChevronRight, FolderPlus } from "lucide-react";

import { ConnectAgentButton } from "@/components/connect-agent-button";
import { Card, CardContent } from "@/components/ui/card";
import { listWorkspaces } from "@/lib/api";

export default async function WorkspacesPage() {
  const workspaces = await listWorkspaces();

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Connected agents</h1>
          <p className="text-sm text-muted-foreground">
            Each connected agent has its own deployments and API key.
          </p>
        </div>
        <ConnectAgentButton />
      </div>

      {workspaces.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
            <FolderPlus className="size-8 text-muted-foreground" />
            <p className="font-medium">No connected agents yet</p>
            <p className="max-w-sm text-sm text-muted-foreground">
              Connect a new agent above to start publishing artifacts.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {workspaces.map((workspace) => (
            <Link key={workspace.id} href={`/dashboard/workspaces/${workspace.id}`}>
              <Card className="transition-colors hover:bg-accent">
                <CardContent className="flex items-center justify-between py-4">
                  <p className="font-mono font-medium">/{workspace.slug}</p>
                  <ChevronRight className="size-4 text-muted-foreground" />
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
