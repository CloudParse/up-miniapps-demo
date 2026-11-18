import { devUserAtom } from "@app/atoms/devSession";
import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { APP_CONFIG } from "@app/config/env";
import { useAtom } from "jotai";
import { saveUser } from "./devHub";

// Development only: shows the test user and goes back to the picker.
export function DevUserSwitchCard() {
  const [user, setUser] = useAtom(devUserAtom);
  if (!APP_CONFIG.isDev || !user) return null;
  return (
    <Card className="flex items-center justify-between gap-3">
      <p className="text-sm-plus text-ink-soft">
        Test : {user.firstName} {user.lastName}
      </p>
      <Button
        onClick={() => {
          saveUser(null);
          setUser(null);
        }}
        size="sm"
        variant="outline"
      >
        Changer
      </Button>
    </Card>
  );
}
