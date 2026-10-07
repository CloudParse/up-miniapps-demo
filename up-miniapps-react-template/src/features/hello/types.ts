/** Wire shape returned by `GET /hello` (see up-miniapps-template-python-backend/app/schemas/hello.py). */
export interface IBackendGreeting {
  message: string;
}

/** What the UI works with. */
export interface Greeting {
  message: string;
}
