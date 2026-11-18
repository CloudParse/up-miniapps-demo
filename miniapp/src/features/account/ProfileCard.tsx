import { avatarAtom, profileAtom } from "@app/atoms/account";
import { Badge } from "@app/components/ui/badge";
import { Card } from "@app/components/ui/card";
import { SkeletonBlock } from "@app/components/ui/skeleton";
import type { IUserProfile } from "@cloudparse/up-miniapps-sdk";
import { useAtomValue } from "jotai";

const REGISTRATION_LABELS: Record<IUserProfile["registrationType"], string> = {
  apple: "Connexion Apple",
  google: "Connexion Google",
  up: "Compte Up",
};

export function ProfileCard() {
  const profile = useAtomValue(profileAtom);
  const avatar = useAtomValue(avatarAtom);

  if (profile.status === "loading" || profile.status === "idle") {
    return (
      <Card className="flex items-center gap-4">
        <SkeletonBlock className="h-16 w-16 rounded-3xl" />
        <div className="flex flex-1 flex-col gap-2">
          <SkeletonBlock className="h-4 w-32" />
          <SkeletonBlock className="h-3 w-20" />
        </div>
      </Card>
    );
  }

  if (profile.status === "error") {
    return (
      <Card className="text-sm-plus text-accent-danger">
        Profil indisponible : {profile.message}
      </Card>
    );
  }

  const data = profile.data;
  const registration = data.registrationType;

  return (
    <Card className="flex items-center gap-4">
      {avatar.status === "ready" && avatar.data ? (
        <img
          alt=""
          className="h-16 w-16 shrink-0 rounded-3xl object-cover"
          src={avatar.data}
        />
      ) : (
        <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-3xl bg-brand-card-strong font-display text-md-plus font-semibold text-ink-soft">
          {(data.firstName ?? "?").slice(0, 1).toUpperCase()}
        </div>
      )}
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <p className="truncate font-display text-md-plus font-semibold text-ink-bright">
          {data.fullName ?? "Utilisateur"}
        </p>
        {data.username ? (
          <p className="truncate text-xs-plus text-ink-faint">
            @{data.username}
          </p>
        ) : null}
        <div className="mt-1 flex flex-wrap gap-2">
          {registration ? (
            <Badge tone="primary">{REGISTRATION_LABELS[registration]}</Badge>
          ) : null}
          {data.admin ? <Badge tone="warning">Admin</Badge> : null}
        </div>
      </div>
    </Card>
  );
}
