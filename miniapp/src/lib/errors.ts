export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "string") return error;
  if (error && typeof error === "object" && "error" in error) {
    const inner: unknown = error.error;
    if (typeof inner === "string") return inner;
  }
  return "Une erreur inattendue est survenue.";
}
