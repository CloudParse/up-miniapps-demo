import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { Input } from "@app/components/ui/input";
import { SkeletonBlock } from "@app/components/ui/skeleton";
import { getQrCodeDataUrl } from "@app/features/media/qrCodeCache";
import { useAction } from "@app/hooks/useAction";
import { getErrorMessage } from "@app/lib/errors";
import { sdk } from "@cloudparse/up-miniapps-sdk";
import { useEffect, useState } from "react";

const DEFAULT_VALUE = "up://demo";

export function QrGenerator() {
  const [value, setValue] = useState(DEFAULT_VALUE);
  const [dataUrl, setDataUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const save = useAction((url: string) => sdk.media.saveImage(url, "demo-qr"));

  useEffect(() => {
    let cancelled = false;
    setIsGenerating(true);
    getQrCodeDataUrl(DEFAULT_VALUE)
      .then((url) => {
        if (!cancelled) setDataUrl(url);
      })
      .catch((cause: unknown) => {
        if (!cancelled) setError(getErrorMessage(cause));
      })
      .finally(() => {
        if (!cancelled) setIsGenerating(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const generate = async () => {
    setIsGenerating(true);
    setError(null);
    try {
      setDataUrl(await getQrCodeDataUrl(value.trim() || DEFAULT_VALUE));
    } catch (cause) {
      setError(getErrorMessage(cause));
    } finally {
      setIsGenerating(false);
    }
  };

  return (
    <Card className="flex flex-col gap-4">
      <p className="font-display text-md-plus font-semibold text-ink-bright">
        Générer un QR code
      </p>
      <div className="flex gap-2">
        <Input
          aria-label="Contenu du QR code"
          onChange={(event) => setValue(event.target.value)}
          value={value}
        />
        <Button onClick={() => void generate()} variant="secondary">
          Générer
        </Button>
      </div>
      <div className="flex justify-center">
        {isGenerating ? (
          <SkeletonBlock className="h-56 w-56" />
        ) : dataUrl ? (
          <img
            alt="QR code généré"
            className="h-56 w-56 rounded-3xl bg-white p-3"
            src={dataUrl}
          />
        ) : null}
      </div>
      {error ? (
        <p className="text-xs-plus text-accent-danger">{error}</p>
      ) : null}
      <Button
        disabled={!dataUrl || save.state.status === "pending"}
        onClick={() => dataUrl && void save.run(dataUrl)}
        variant="outline"
      >
        Enregistrer dans la galerie
      </Button>
      {save.state.status === "success" ? (
        <p className="text-xs-plus text-accent-success">
          {save.state.result.success
            ? "Image enregistrée."
            : "Enregistrement refusé."}
        </p>
      ) : null}
      {save.state.status === "error" ? (
        <p className="text-xs-plus text-accent-danger">{save.state.message}</p>
      ) : null}
    </Card>
  );
}
