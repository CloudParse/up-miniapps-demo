import { type SDKEvent, sdk } from "@cloudparse/up-miniapps-sdk";
import { useEffect, useRef } from "react";

// Subscribes to one shell event for the component's lifetime. The handler is
// read through a ref, so an inline callback never causes a re-subscribe.
export function useSdkEvent<T = unknown>(
  event: SDKEvent,
  handler: (data: T) => void,
) {
  const handlerRef = useRef(handler);

  useEffect(() => {
    handlerRef.current = handler;
  });

  useEffect(
    () => sdk.on<T>(event, (data) => handlerRef.current(data)),
    [event],
  );
}
