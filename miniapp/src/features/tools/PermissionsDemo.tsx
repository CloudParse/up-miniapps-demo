import { ScreenTitle } from "@app/components/layout/ScreenTitle";
import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { useAction } from "@app/hooks/useAction";
import { sdk } from "@cloudparse/up-miniapps-sdk";

function resultLabel(
  state: ReturnType<typeof useAction<[], boolean>>["state"],
): string | null {
  if (state.status === "pending") return "Demande en cours…";
  if (state.status === "error") return state.message;
  if (state.status === "success") return state.result ? "Accordée" : "Refusée";
  return null;
}

export function PermissionsDemo() {
  const camera = useAction(() => sdk.permission.request("camera"));
  const location = useAction(() => sdk.permission.request("location"));
  const profile = useAction(() =>
    sdk.permission.request("profile", ["fullName"]),
  );

  const rows = [
    { action: camera, label: "Caméra", run: () => void camera.run() },
    { action: location, label: "Localisation", run: () => void location.run() },
    {
      action: profile,
      label: "Profil (nom complet)",
      run: () => void profile.run(),
    },
  ];

  return (
    <div className="flex flex-col gap-4">
      <ScreenTitle
        subtitle="Chaque demande ouvre le dialogue natif du téléphone."
        title="Permissions"
      />
      {rows.map((row) => (
        <Card className="flex flex-col gap-3" key={row.label}>
          <div className="flex items-center justify-between gap-3">
            <p className="text-sm-plus font-medium text-ink-bright">
              {row.label}
            </p>
            <Button onClick={row.run} size="sm" variant="secondary">
              Demander
            </Button>
          </div>
          {resultLabel(row.action.state) ? (
            <p className="text-xs-plus text-ink-soft">
              {resultLabel(row.action.state)}
            </p>
          ) : null}
        </Card>
      ))}
    </div>
  );
}
