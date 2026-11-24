import { APP_CONFIG } from "@app/config/env";
import { BRAND_COLORS } from "@app/utils/constants/brand";
import { type IGenerateQrCodeOptions, sdk } from "@cloudparse/up-miniapps-sdk";

export const QR_OPTIONS: IGenerateQrCodeOptions = {
  appName: APP_CONFIG.appName,
  backgroundColor: BRAND_COLORS.surface,
  dotsGradient: {
    colorStops: [
      { color: BRAND_COLORS.accentPrimary, offset: 0 },
      { color: BRAND_COLORS.accentSecondary, offset: 1 },
    ],
    rotation: 0.8,
    type: "linear",
  },
  dotsType: "rounded",
  errorCorrectionLevel: "H",
  // Empty on purpose: no center logo. The QR library loads a logo through an XMLHttpRequest
  // on its URL, and the host's CSP `connect-src` blocks that request for `data:` URLs (the
  // inlined logo, and the SDK's default logo). The code is generated and read the same
  // without it. `""` (not `undefined`) switches the default logo off: `null` is not typed.
  logo: "",
  size: 512,
};

const resultCache = new Map<string, string>();
const inFlight = new Map<string, Promise<string>>();

// Route every QR generation through here: a shared cache plus in-flight dedupe,
// so re-rendering or re-tapping never regenerates the same code.
export function getQrCodeDataUrl(data: string): Promise<string> {
  const key = data;
  const cached = resultCache.get(key);
  if (cached) return Promise.resolve(cached);
  const pending = inFlight.get(key);
  if (pending) return pending;

  const request = sdk.qrCode
    .generate(data, QR_OPTIONS)
    .then((dataUrl) => {
      resultCache.set(key, dataUrl);
      inFlight.delete(key);
      return dataUrl;
    })
    .catch((error: unknown) => {
      inFlight.delete(key);
      throw error;
    });

  inFlight.set(key, request);
  return request;
}
