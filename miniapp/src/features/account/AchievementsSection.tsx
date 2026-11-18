import {
  achievementsAtom,
  currentAchievementPriorityAtom,
  orderedAchievementsAtom,
} from "@app/atoms/account";
import { EmptyState } from "@app/components/layout/EmptyState";
import { Badge } from "@app/components/ui/badge";
import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { Input } from "@app/components/ui/input";
import { SkeletonBlock } from "@app/components/ui/skeleton";
import { useAction } from "@app/hooks/useAction";
import {
  type IAchievement,
  ParticleShower,
  sdk,
} from "@cloudparse/up-miniapps-sdk";
import { useAtomValue } from "jotai";
import { Lock } from "lucide-react";
import { useState } from "react";

const UNLOCK_FOOTER =
  "Tes succès se débloquent automatiquement dès que l'action demandée est accomplie.";

function progressPercent(achievement: IAchievement): number {
  if (achievement.totalActionCount <= 0) return 0;
  const ratio = achievement.playerActionCount / achievement.totalActionCount;
  return Math.min(100, Math.round(ratio * 100));
}

const CELEBRATION_DURATION_MS = 2200;

export function AchievementsSection() {
  const state = useAtomValue(achievementsAtom);
  const ordered = useAtomValue(orderedAchievementsAtom);
  const currentPriority = useAtomValue(currentAchievementPriorityAtom);
  const [showCelebration, setShowCelebration] = useState(false);

  return (
    <section className="flex flex-col gap-3">
      <h2 className="font-display text-xl-plus font-semibold text-ink-bright">
        Succès
      </h2>

      {/* ParticleShower demo: a pure rendering primitive with no visibility/
          timing state of its own (see the SDK's own doc comment) — this is
          the "caller decides when to mount it and for how long" pattern the
          SDK itself documents, triggered on demand rather than tied to a
          real unlock event, same as SingleAchievementLookup below is a
          self-contained interactive demo rather than live data. */}
      <Card className="flex items-center justify-between gap-3" tone="strong">
        <p className="text-sm-plus font-semibold text-ink-bright">
          Effet de célébration (ParticleShower)
        </p>
        <Button
          onClick={() => {
            setShowCelebration(true);
            setTimeout(
              () => setShowCelebration(false),
              CELEBRATION_DURATION_MS,
            );
          }}
          variant="secondary"
        >
          Essayer
        </Button>
      </Card>
      {showCelebration ? (
        <ParticleShower count={24} emoji={["🏆", "⭐", "🎉"]} />
      ) : null}

      {state.status === "loading" || state.status === "idle" ? (
        <div className="flex flex-col gap-3">
          <SkeletonBlock className="h-20" />
          <SkeletonBlock className="h-20" />
        </div>
      ) : null}

      {state.status === "error" ? (
        <p className="text-sm-plus text-accent-danger">{state.message}</p>
      ) : null}

      {state.status === "ready" && ordered.length === 0 ? (
        <EmptyState
          description="Les succès apparaîtront ici dès que le backend en aura défini."
          title="Aucun succès"
        />
      ) : null}

      {ordered.map((achievement) => {
        const isLocked =
          !achievement.completed && achievement.priority > currentPriority;
        return (
          <Card className="flex gap-3" key={achievement.slug}>
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-brand-card-strong text-ink-soft">
              {isLocked ? (
                <Lock size={20} />
              ) : (
                <span className="text-md-plus font-semibold">
                  {achievement.priority}
                </span>
              )}
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center justify-between gap-2">
                <p className="truncate text-sm-plus font-semibold text-ink-bright">
                  {isLocked ? "Succès verrouillé" : achievement.title}
                </p>
                {achievement.completed ? (
                  <Badge tone="success">
                    Débloqué · +{achievement.pointsReward} pts
                  </Badge>
                ) : null}
              </div>
              {isLocked ? null : (
                <>
                  <p className="mt-1 text-xs-plus text-ink-soft">
                    {achievement.description}
                  </p>
                  <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-brand-card-strong">
                    <div
                      className="h-full rounded-full bg-accent-primary transition-all"
                      style={{ width: `${progressPercent(achievement)}%` }}
                    />
                  </div>
                  <p className="mt-1 text-xs-plus text-ink-faint">
                    {achievement.playerActionCount} /{" "}
                    {achievement.totalActionCount}
                  </p>
                </>
              )}
            </div>
          </Card>
        );
      })}

      {state.status === "ready" && ordered.length > 0 ? (
        <p className="text-xs-plus text-ink-faint">{UNLOCK_FOOTER}</p>
      ) : null}

      <SingleAchievementLookup fallbackSlug={ordered[0]?.slug ?? ""} />
    </section>
  );
}

function SingleAchievementLookup({ fallbackSlug }: { fallbackSlug: string }) {
  const [slug, setSlug] = useState("");
  const lookup = useAction((value: string) => sdk.achievement(value));
  const effectiveSlug = slug || fallbackSlug;

  return (
    <Card className="flex flex-col gap-3" tone="strong">
      <p className="text-sm-plus font-semibold text-ink-bright">
        Consulter un succès par slug
      </p>
      <div className="flex gap-2">
        <Input
          aria-label="Slug du succès"
          onChange={(event) => setSlug(event.target.value)}
          placeholder={fallbackSlug || "ex. first-journey"}
          value={slug}
        />
        <Button
          onClick={() => void lookup.run(effectiveSlug)}
          variant="secondary"
        >
          Voir
        </Button>
      </div>
      {lookup.state.status === "success" ? (
        <p className="text-xs-plus text-ink-soft">
          {lookup.state.result.title} —{" "}
          {lookup.state.result.completed ? "débloqué" : "en cours"} (
          {lookup.state.result.playerActionCount}/
          {lookup.state.result.totalActionCount})
        </p>
      ) : null}
      {lookup.state.status === "error" ? (
        <p className="text-xs-plus text-accent-danger">
          {lookup.state.message}
        </p>
      ) : null}
    </Card>
  );
}
