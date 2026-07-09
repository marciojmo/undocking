"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { Pencil } from "lucide-react";

import { updateWorkspaceSlugAction } from "@/app/dashboard/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export function EditableSlug({
  workspaceId,
  initialSlug,
}: {
  workspaceId: string;
  initialSlug: string;
}) {
  const router = useRouter();
  const [slug, setSlug] = useState(initialSlug);
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState(initialSlug);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  function startEditing() {
    setValue(slug);
    setError(null);
    setEditing(true);
  }

  function cancelEditing() {
    setValue(slug);
    setError(null);
    setEditing(false);
  }

  function handleChange(next: string) {
    setValue(next);
    if (error) setError(null);
  }

  function handleSave() {
    const trimmed = value.trim();
    if (!trimmed || trimmed === slug) {
      setEditing(false);
      return;
    }
    startTransition(async () => {
      const result = await updateWorkspaceSlugAction(workspaceId, trimmed);
      if (!result.ok) {
        setError(result.error);
        return;
      }
      setSlug(result.data.slug);
      setEditing(false);
      router.refresh();
    });
  }

  if (!editing) {
    return (
      <div className="flex items-center gap-2">
        <h1 className="font-mono text-2xl font-bold tracking-tight">/{slug}</h1>
        <button
          type="button"
          onClick={startEditing}
          className="text-sm text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
        >
          Edit
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        <Pencil className="size-4 text-muted-foreground" />
        <Input
          value={value}
          onChange={(event) => handleChange(event.target.value)}
          maxLength={64}
          aria-invalid={error ? true : undefined}
          autoFocus
          className="font-mono sm:w-72"
        />
        <Button size="sm" onClick={handleSave} disabled={pending || !value.trim()}>
          Save
        </Button>
        <Button size="sm" variant="outline" onClick={cancelEditing} disabled={pending}>
          Cancel
        </Button>
      </div>
      {error ? (
        <p className="text-xs text-destructive">{error}</p>
      ) : (
        <p className="text-xs text-muted-foreground">
          Changing this will break any existing shared links to this agent&apos;s
          deployments.
        </p>
      )}
    </div>
  );
}
