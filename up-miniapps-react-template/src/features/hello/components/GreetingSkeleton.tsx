import { SkeletonBlock } from "@app/components/ui/skeleton";

// Same loose shape as GreetingCard: icon, headline, endpoint badge.
export function GreetingSkeleton() {
  return (
    <div className="flex flex-col items-center gap-5">
      <SkeletonBlock className="h-12 w-12" />
      <SkeletonBlock className="h-10 w-64" />
      <SkeletonBlock className="h-7 w-32 rounded-full" />
    </div>
  );
}
