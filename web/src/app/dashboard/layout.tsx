import Link from "next/link";
import { redirect } from "next/navigation";
import { Rocket } from "lucide-react";

import { LogoutButton } from "@/components/logout-button";
import { getCurrentUser } from "@/lib/api";
import { isMockApiEnabled } from "@/lib/dev-mocks";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/");

  const mockApi = isMockApiEnabled();

  return (
    <div className="flex min-h-full flex-1 flex-col">
      {mockApi ? (
        <div className="border-b border-amber-500/30 bg-amber-500/10 px-6 py-2 text-center text-sm text-amber-200">
          Mock API — changes are not persisted to a real backend.
        </div>
      ) : null}
      <header className="border-b">
        <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-4">
          <Link href="/dashboard" className="flex items-center gap-2 font-semibold">
            <Rocket className="size-5" />
            Ship
          </Link>
          <div className="flex items-center gap-4">
            <span className="hidden text-sm text-muted-foreground sm:inline">
              {user.email}
            </span>
            <LogoutButton />
          </div>
        </div>
      </header>
      <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-10">{children}</main>
    </div>
  );
}
