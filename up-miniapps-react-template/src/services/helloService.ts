import type { Greeting, IBackendGreeting } from "@app/features/hello/types";
import { apiService } from "@app/services/apiService";

export const HELLO_ENDPOINT = "/hello";

// The one place wire shapes become UI shapes, so a backend rename touches
// this file only.
function mapBackendGreeting(greeting: IBackendGreeting): Greeting {
  return { message: greeting.message };
}

export async function fetchGreeting(): Promise<Greeting> {
  const greeting = await apiService.get<IBackendGreeting>(HELLO_ENDPOINT);
  return mapBackendGreeting(greeting);
}
