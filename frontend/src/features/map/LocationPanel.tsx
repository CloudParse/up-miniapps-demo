import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { Switch } from "@app/components/ui/switch";
import { useAction } from "@app/hooks/useAction";
import { sdk, useUserLocation } from "@cloudparse/up-miniapps-sdk";
import { useState } from "react";

export function LocationPanel() {
  const live = useUserLocation();
  const [isStreaming, setIsStreaming] = useState(false);
  const position = useAction(() => sdk.location.getCurrentPosition());

  const toggleStream = (next: boolean) => {
    setIsStreaming(next);
    if (next) {
      void sdk.location.startStream({ distanceFilter: 5, interval: 1000 });
    } else {
      void sdk.location.stopStream();
    }
  };

  return (
    <Card className="flex flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm-plus font-semibold text-ink-bright">Position</p>
          <p className="text-xs-plus text-ink-soft">
            {live.coords
              ? `${live.coords[1].toFixed(5)}, ${live.coords[0].toFixed(5)}`
              : "En attente d'une position…"}
          </p>
        </div>
        <label className="flex items-center gap-2 text-xs-plus text-ink-soft">
          Flux GPS
          <Switch
            aria-label="Flux de localisation"
            checked={isStreaming}
            onCheckedChange={toggleStream}
          />
        </label>
      </div>
      <Button onClick={() => void position.run()} size="sm" variant="secondary">
        Position ponctuelle
      </Button>
      {position.state.status === "success" ? (
        <p className="text-xs-plus text-ink-soft">
          Précision {position.state.result.coords.accuracy ?? "?"} m
        </p>
      ) : null}
      {position.state.status === "error" ? (
        <p className="text-xs-plus text-accent-danger">
          {position.state.message}
        </p>
      ) : null}
    </Card>
  );
}
