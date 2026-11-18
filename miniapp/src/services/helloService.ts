import { apiService } from "@app/services/backend";

// Public route of the demo backend (backend/app/api/routes/hello.py), served under /api/v1.
export const HELLO_PATH = "hello";

/** Wire shape returned by `GET /api/v1/hello` (backend/app/schemas/hello.py). */
interface IBackendGreeting {
  message: string;
}

export interface Greeting {
  message: string;
}

// The one place the wire shape becomes the UI shape.
function mapBackendGreeting(greeting: IBackendGreeting): Greeting {
  return { message: greeting.message };
}

export async function fetchGreeting(): Promise<Greeting> {
  return mapBackendGreeting(await apiService.get<IBackendGreeting>(HELLO_PATH));
}
