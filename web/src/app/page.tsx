import { redirect } from "next/navigation";
import { Rocket, Terminal, KeyRound, Zap } from "lucide-react";

import { SignInButtons } from "@/components/sign-in-buttons";
import { getCurrentUser, getProviders } from "@/lib/api";

const FEATURES = [
  {
    icon: Terminal,
    title: "One call to publish",
    body: "POST HTML or Markdown over REST or MCP and get back a public URL. No build step, no config.",
  },
  {
    icon: Zap,
    title: "Instant public URLs",
    body: "Content is served at /{workspace}/{slug} the moment you deploy it — shareable immediately.",
  },
  {
    icon: KeyRound,
    title: "Built for agents",
    body: "Scoped bearer keys and native MCP tools mean your agents can ship artifacts on their own.",
  },
];

export default async function LandingPage() {
  const user = await getCurrentUser();
  if (user) redirect("/dashboard");

  const providers = await getProviders();

  return (
    <main className="flex flex-1 flex-col">
      <header className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2 font-semibold">
          <Rocket className="size-5" />
          Ship
        </div>
      </header>

      <section className="mx-auto flex w-full max-w-5xl flex-1 flex-col items-center gap-12 px-6 py-16 text-center">
        <div className="flex flex-col items-center gap-6">
          <span className="rounded-full border px-3 py-1 text-xs font-medium text-muted-foreground">
            Deploy artifacts in a single call
          </span>
          <h1 className="max-w-3xl text-4xl font-bold tracking-tight sm:text-6xl">
            Ship HTML &amp; Markdown to a public URL
          </h1>
          <p className="max-w-2xl text-lg text-muted-foreground">
            Ship is a deployment platform for HTML and Markdown artifacts. Upload
            content over REST or MCP, get back a link, and share it instantly —
            designed from the ground up for AI agents.
          </p>
          <div className="flex flex-col items-center gap-3 pt-2">
            <SignInButtons providers={providers} />
            <p className="text-xs text-muted-foreground">
              Sign in to create a workspace and get an API key.
            </p>
          </div>
        </div>

        <div className="grid w-full gap-6 sm:grid-cols-3">
          {FEATURES.map((feature) => (
            <div
              key={feature.title}
              className="flex flex-col items-start gap-3 rounded-xl border p-6 text-left"
            >
              <feature.icon className="size-5" />
              <h2 className="font-semibold">{feature.title}</h2>
              <p className="text-sm text-muted-foreground">{feature.body}</p>
            </div>
          ))}
        </div>
      </section>

      <footer className="mx-auto w-full max-w-5xl px-6 py-8 text-center text-xs text-muted-foreground">
        Ship — open-source deployment platform for agents.
      </footer>
    </main>
  );
}
