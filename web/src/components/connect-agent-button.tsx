"use client";

import { useTransition } from "react";
import { useRouter } from "next/navigation";
import { Plus } from "lucide-react";
import { toast } from "sonner";

import { connectAgentAction } from "@/app/dashboard/actions";
import { Button } from "@/components/ui/button";

export function ConnectAgentButton() {
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  function handleClick() {
    startTransition(async () => {
      const result = await connectAgentAction();
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      sessionStorage.setItem(`pending-key:${result.data.workspace.id}`, result.data.key.key);
      router.push(`/dashboard/workspaces/${result.data.workspace.id}`);
    });
  }

  return (
    <Button onClick={handleClick} disabled={pending}>
      <Plus className="size-4" />
      Connect a new agent
    </Button>
  );
}
