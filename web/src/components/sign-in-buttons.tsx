import { LogIn } from "lucide-react";

import { Button } from "@/components/ui/button";

const PROVIDER_LABELS: Record<string, string> = {
  github: "Continue with GitHub",
  google: "Continue with Google",
};

/**
 * Renders a sign-in link per configured OAuth provider. These are full-page
 * navigations to the backend (via the /api proxy), which runs the OAuth dance.
 */
export function SignInButtons({ providers }: { providers: string[] }) {
  if (providers.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No sign-in providers are configured. Set the OAuth credentials in the API
        environment to enable sign-in.
      </p>
    );
  }

  return (
    <div className="flex w-full flex-col gap-3 sm:w-auto">
      {providers.map((provider) => (
        <Button
          key={provider}
          size="lg"
          className="w-full sm:w-72"
          render={<a href={`/api/auth/login/${provider}`} />}
        >
          <LogIn className="size-4" />
          {PROVIDER_LABELS[provider] ?? `Continue with ${provider}`}
        </Button>
      ))}
    </div>
  );
}
