import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { TEST_USERS, type TestUser } from "./devHub";

export interface DevUserPickerProps {
  pending: TestUser | null;
  error: string;
  onPick: (user: TestUser | null) => void;
}

// Development only: the simulator signs in as one of the DEV backend's test
// users, so every authenticated route gets a real Hub token.
export function DevUserPicker({ error, onPick, pending }: DevUserPickerProps) {
  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto bg-brand-bg px-4 py-6 text-ink-bright">
      <div>
        <p className="font-display text-xl-plus font-semibold">
          Utilisateur de test
        </p>
        <p className="mt-1 text-sm-plus text-ink-soft">
          Développement uniquement : choisis le compte du backend DEV avec
          lequel le simulateur se connecte.
        </p>
      </div>
      {error ? (
        <Card className="text-sm-plus text-accent-danger">
          Connexion impossible : {error}
        </Card>
      ) : null}
      <div className="flex flex-col gap-2">
        {TEST_USERS.map((user) => (
          <Button
            disabled={pending !== null && !error}
            key={user.localNumber}
            onClick={() => onPick(user)}
            variant={pending === user ? "primary" : "secondary"}
          >
            {user.firstName} {user.lastName}
          </Button>
        ))}
      </div>
      {pending ? (
        <Button onClick={() => onPick(null)} variant="ghost">
          Annuler
        </Button>
      ) : null}
    </div>
  );
}
