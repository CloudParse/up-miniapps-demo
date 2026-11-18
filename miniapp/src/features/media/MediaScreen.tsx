import { ScreenTitle } from "@app/components/layout/ScreenTitle";
import { QrDecoder } from "@app/features/media/QrDecoder";
import { QrGenerator } from "@app/features/media/QrGenerator";
import { QrScannerDemo } from "@app/features/media/QrScannerDemo";

export function MediaScreen() {
  return (
    <div className="flex-1 overflow-y-auto px-4 pt-1 pb-6">
      <div className="flex flex-col gap-5">
        <ScreenTitle
          subtitle="QR codes, lecture par image et caméra, galerie."
          title="Médias"
        />
        <QrGenerator />
        <QrDecoder />
        <QrScannerDemo />
      </div>
    </div>
  );
}
