import { ScreenTitle } from "@app/components/layout/ScreenTitle";
import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { DEMO_POIS } from "@app/config/demo";
import { useAction } from "@app/hooks/useAction";
import { sdk } from "@cloudparse/up-miniapps-sdk";

const ORIGIN = DEMO_POIS[0];
const DESTINATION = DEMO_POIS[1];

// getRoute asks the routing backend (see sdk.config in App.tsx), drawRoute shows the result on
// the host map, clearRoute removes it. useJourney (Map tab) does the three steps for a journey.
async function drawDemoRoute() {
  const route = await sdk.routing.getRoute({
    destination: [DESTINATION.longitude, DESTINATION.latitude],
    origin: [ORIGIN.longitude, ORIGIN.latitude],
    profile: "walking",
  });
  await sdk.routing.drawRoute(route);
  return route;
}

export function RoutingDemo() {
  const draw = useAction(drawDemoRoute);
  const clear = useAction(() => sdk.routing.clearRoute());

  return (
    <div className="flex flex-col gap-4">
      <ScreenTitle
        subtitle="Calcule un itinéraire, trace-le sur la carte du shell, puis efface-le."
        title="Itinéraire"
      />
      <Card className="flex flex-col gap-3">
        <p className="text-sm-plus text-ink-bright">
          {ORIGIN.name} vers {DESTINATION.name} (à pied)
        </p>
        <div className="grid grid-cols-2 gap-2">
          <Button
            disabled={draw.state.status === "pending"}
            onClick={() => void draw.run()}
            variant="secondary"
          >
            Tracer
          </Button>
          <Button
            disabled={clear.state.status === "pending"}
            onClick={() => void clear.run()}
            variant="outline"
          >
            Effacer
          </Button>
        </div>
        {draw.state.status === "success" ? (
          <p className="text-xs-plus text-accent-success">
            {Math.round(draw.state.result.distanceMeters)} m,{" "}
            {Math.round(draw.state.result.durationSeconds / 60)} min.
          </p>
        ) : null}
        {draw.state.status === "error" ? (
          <p className="text-xs-plus text-accent-danger">
            {draw.state.message}
          </p>
        ) : null}
        {clear.state.status === "error" ? (
          <p className="text-xs-plus text-accent-danger">
            {clear.state.message}
          </p>
        ) : null}
      </Card>
    </div>
  );
}
