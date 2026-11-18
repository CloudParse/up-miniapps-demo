import { sdk } from "@cloudparse/up-miniapps-sdk";

// Thin wrappers over the SDK so screens never import the SDK namespaces directly
// for account data. Swap or extend here, not in components.
export const accountService = {
  getBalance: () => sdk.fidelity.getFidelityBalance(),
  getHistory: (limit: number) => sdk.fidelity.getFidelityHistory({ limit }),
  getPicture: () => sdk.user.getProfilePicture(),
  getProfile: () =>
    sdk.user.getProfile([
      "uuid",
      "fullName",
      "firstName",
      "username",
      "registrationType",
      "countryCode",
      "createdAt",
      "admin",
    ]),
};
