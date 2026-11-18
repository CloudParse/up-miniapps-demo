import { Button } from "@app/components/ui/button";
import { Card } from "@app/components/ui/card";
import { useAction } from "@app/hooks/useAction";
import { sdk } from "@cloudparse/up-miniapps-sdk";

async function pickAndDecode(): Promise<string | null> {
  const picked = await sdk.media.pickImage();
  if (!picked.success || !picked.base64) return null;
  const mimeType = picked.mimeType ?? "image/png";
  return sdk.qrCode.decode(`data:${mimeType};base64,${picked.base64}`);
}

export function QrDecoder() {
  const decode = useAction(pickAndDecode);

  return (
    <Card className="flex flex-col gap-3">
      <p className="font-display text-md-plus font-semibold text-ink-bright">
        Lire un QR depuis une photo
      </p>
      <Button
        disabled={decode.state.status === "pending"}
        onClick={() => void decode.run()}
        variant="secondary"
      >
        Choisir une image
      </Button>
      {decode.state.status === "success" ? (
        <p className="break-all text-sm-plus text-ink-soft">
          {decode.state.result ?? "Aucun QR code trouvé dans cette image."}
        </p>
      ) : null}
      {decode.state.status === "error" ? (
        <p className="text-xs-plus text-accent-danger">
          {decode.state.message}
        </p>
      ) : null}
    </Card>
  );
}
