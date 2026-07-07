import { redirect } from "next/navigation";
import { Anchor, Terminal, Link } from "lucide-react";

import { SignInButtons } from "@/components/sign-in-buttons";
import { getCurrentUser, getProviders } from "@/lib/api";

const FEATURES = [
  {
    icon: Terminal,
    title: "Connect",
    body: "Paste a prompt to connect your agent to Undocking.",
  },
  {
    icon: Anchor,
    title: "Undock",
    body: "Ask your agent to undock their generated content. Free yourself from manual deployment.",
  },
  {
    icon: Link,
    title: "Share",
    body: "Get an instant public link to your content. Share it with the world.",
  },
];

export default async function LandingPage() {
  const user = await getCurrentUser();
  if (user) redirect("/dashboard");

  const providers = await getProviders();

  return (
    <div className="dark flex flex-1 flex-col bg-black text-white">
      <div
        className="relative flex min-h-svh flex-col"
        style={{
          backgroundImage: "url('/hero.jpg')",
          backgroundSize: "cover",
          backgroundPosition: "center 50%",
        }}
      >
        <div className="absolute inset-0 bg-gradient-to-b from-black/60 via-black/20 to-black/80" />

        <header className="relative z-10 mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-6">
          <div className="flex items-center gap-2 font-semibold">
            <Anchor className="size-4" />
            Undocking
          </div>
          <a
            href="https://github.com/marciojmo/undocking"
            className="text-sm text-white/60 transition-colors hover:text-white"
          >
            View on GitHub
          </a>
        </header>

        <div className="relative z-10 flex flex-1 flex-col items-center justify-center px-6 pb-32 text-center">
          <span className="mb-8 rounded-full border border-white/20 bg-white/5 px-3 py-1 text-xs text-white/60">
            Open-source content deployment platform for AI agents.
          </span>
          <h1 className="max-w-3xl text-5xl font-bold tracking-tight sm:text-7xl">
            Publish agent generated content to the web
          </h1>
          <p className="mt-6 max-w-lg text-lg text-white/60">
            From your AI agent to a public, shareable link.
          </p>
          <div className="mt-8 flex flex-col items-center gap-3">
            <SignInButtons providers={providers} />
            <p className="text-xs text-white/30">
              Sign in to connect your agent to Undocking.
            </p>
          </div>
        </div>
      </div>

      {/* Feature cards below the fold */}
      <div className="px-6 py-24">
        <div className="mx-auto grid w-full max-w-5xl gap-6 sm:grid-cols-3">
          {FEATURES.map((feature, index) => (
            <div
              key={feature.title}
              className="relative flex flex-col items-start gap-3 rounded-xl border border-white/10 bg-white/5 p-6 text-left"
            >
              <feature.icon className="size-5 text-white/60" />
              <h2 className="font-semibold">{String(index + 1)}. {feature.title}</h2>
              <p className="text-sm text-white/50">{feature.body}</p>
            </div>
          ))}
        </div>
      </div>

      <footer className="px-6 pb-12 text-center text-xs text-white/25">
        Undocking — open-source content deployment platform for AI agents.
      </footer>
    </div>
  );
}
