import { EndpointBadge } from "@app/features/hello/components/EndpointBadge";
import type { Greeting } from "@app/features/hello/types";
import { Sparkles } from "lucide-react";

export interface GreetingCardProps {
  endpoint: string;
  greeting: Greeting;
}

export function GreetingCard({ endpoint, greeting }: GreetingCardProps) {
  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 flex flex-col items-center gap-5 duration-700">
      <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-accent-primary/15 text-accent-primary">
        <Sparkles size={22} />
      </div>
      <h1 className="bg-linear-to-r from-accent-primary to-accent-secondary bg-clip-text text-center text-display font-semibold leading-tight text-transparent">
        {greeting.message}
      </h1>
      <EndpointBadge method="GET" path={endpoint} />
    </div>
  );
}
