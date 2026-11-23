/** The web launcher answers this for a native-only capability (fidelity, camera, location...). */
const WEB_HOST_UNSUPPORTED = /is not supported by the UP web host/;

export function getErrorMessage(error: unknown): string {
  const message = rawErrorMessage(error);
  return WEB_HOST_UNSUPPORTED.test(message)
    ? "Cette fonction n'existe que dans l'app UP, pas sur le site web."
    : message;
}

function rawErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  if (error && typeof error === "object" && "error" in error) {
    const inner: unknown = error.error;
    if (typeof inner === "string") return inner;
  }
  return "Une erreur inattendue est survenue.";
}
