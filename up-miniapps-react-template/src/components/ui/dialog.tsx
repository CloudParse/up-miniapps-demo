import { cn } from "@app/lib/utils";
import { usePhoneContainer } from "@cloudparse/up-miniapps-sdk";
import { Dialog as DialogPrimitive } from "radix-ui";
import type { ReactNode } from "react";

export interface DialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children?: ReactNode;
  className?: string;
}

// Dedicated, reusable dialog. Used by every confirmation: never window.confirm.
//
// The portal targets the SDK phone simulator's own screen (`usePhoneContainer`)
// so the overlay stays trapped inside the phone frame. Outside the simulator
// it is `undefined` and Radix falls back to `document.body`, which is correct.
// Sizing uses percentages and `top-1/2`, never viewport units, for the same
// reason: the app's real container is the phone screen, not the browser tab.
export function Dialog({
  children,
  className,
  description,
  onOpenChange,
  open,
  title,
}: DialogProps) {
  const container = usePhoneContainer();
  return (
    <DialogPrimitive.Root onOpenChange={onOpenChange} open={open}>
      <DialogPrimitive.Portal container={container}>
        <DialogPrimitive.Overlay className="fixed inset-0 z-40 bg-black/60 data-[state=open]:animate-in data-[state=open]:fade-in-0" />
        <DialogPrimitive.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 max-h-[85%] w-[calc(100%-2rem)] max-w-sm -translate-x-1/2 -translate-y-1/2 overflow-y-auto rounded-3xl border border-brand-border bg-brand-card p-5 data-[state=open]:animate-in data-[state=open]:fade-in-0 data-[state=open]:zoom-in-95",
            className,
          )}
        >
          <DialogPrimitive.Title className="font-display text-md-plus font-semibold text-ink-bright">
            {title}
          </DialogPrimitive.Title>
          {description ? (
            <DialogPrimitive.Description className="mt-2 text-sm-plus text-ink-soft">
              {description}
            </DialogPrimitive.Description>
          ) : null}
          <div className="mt-5 flex flex-col gap-2">{children}</div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
