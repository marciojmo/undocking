"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Trash2 } from "lucide-react";
import { toast } from "sonner";

import { deleteWorkspaceAction } from "@/app/dashboard/actions";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

export function DeleteWorkspaceButton({
  workspaceId,
  workspaceName,
}: {
  workspaceId: string;
  workspaceName: string;
}) {
  const router = useRouter();
  const [confirming, setConfirming] = useState(false);
  const [pending, startTransition] = useTransition();

  function handleDelete() {
    startTransition(async () => {
      const result = await deleteWorkspaceAction(workspaceId);
      if (!result.ok) {
        setConfirming(false);
        toast.error(result.error);
        return;
      }
      toast.success("Connected agent deleted");
      router.push("/dashboard");
    });
  }

  return (
    <>
      <Button variant="destructive" size="sm" onClick={() => setConfirming(true)}>
        <Trash2 className="size-4" />
        Delete connected agent
      </Button>

      <Dialog open={confirming} onOpenChange={setConfirming}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete {workspaceName}?</DialogTitle>
            <DialogDescription>
              This soft-deletes the connected agent and immediately invalidates
              its API key. This can&apos;t be undone from the dashboard.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setConfirming(false)}>
              Cancel
            </Button>
            <Button variant="destructive" onClick={handleDelete} disabled={pending}>
              <Trash2 className="size-4" />
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
