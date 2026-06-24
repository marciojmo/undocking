"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { toast } from "sonner";

import { createWorkspaceAction } from "@/app/dashboard/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function CreateWorkspaceForm() {
  const [name, setName] = useState("");
  const [pending, startTransition] = useTransition();
  const router = useRouter();

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    startTransition(async () => {
      const result = await createWorkspaceAction(name);
      if (!result.ok) {
        toast.error(result.error);
        return;
      }
      toast.success(`Created “${result.data.name}”`);
      setName("");
      router.push(`/dashboard/workspaces/${result.data.id}`);
    });
  }

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <Input
        value={name}
        onChange={(event) => setName(event.target.value)}
        placeholder="New workspace name"
        maxLength={64}
        className="sm:w-64"
      />
      <Button type="submit" disabled={pending || !name.trim()}>
        Create
      </Button>
    </form>
  );
}
