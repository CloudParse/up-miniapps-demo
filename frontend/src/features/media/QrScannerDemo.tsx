import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { useAction } from "@app/hooks/useAction";
import { QRScanner, sdk } from "@cloudparse/up-miniapps-sdk";
import { useState } from "react";

export function QrScannerDemo() {
  const camera = useAction(() => sdk.permission.request("camera"));
  const [isScanning, setIsScanning] = useState(false);
  const [lastScan, setLastScan] = useState<string | null>(null);
  const [scanError, setScanError] = useState<string | null>(null);

  const openScanner = async () => {
    const granted = await camera.run();
    if (granted) setIsScanning(true);
  };

  return (
    <Card className="flex flex-col gap-3">
      <p className="font-display text-md-plus font-semibold text-ink-bright">
        Scanner en direct
      </p>
      {isScanning ? (
        <div className="overflow-hidden rounded-3xl">
          <QRScanner
            className="aspect-square w-full"
            onError={(message) => setScanError(message)}
            onScan={(data) => {
              setLastScan(data);
              setIsScanning(false);
            }}
          />
        </div>
      ) : (
        <Button
          disabled={camera.state.status === "pending"}
          onClick={() => void openScanner()}
          variant="secondary"
        >
          Ouvrir la caméra
        </Button>
      )}
      {isScanning ? (
        <Button onClick={() => setIsScanning(false)} variant="ghost">
          Arrêter
        </Button>
      ) : null}
      {camera.state.status === "success" && !camera.state.result ? (
        <p className="text-xs-plus text-accent-danger">
          Accès à la caméra refusé.
        </p>
      ) : null}
      {lastScan ? (
        <p className="break-all text-sm-plus text-ink-soft">
          Dernier scan : {lastScan}
        </p>
      ) : null}
      {scanError ? (
        <p className="text-xs-plus text-accent-danger">{scanError}</p>
      ) : null}
    </Card>
  );
}
