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
// `container={usePhoneContainer()}`: Radix portals to `document.body` by
// default, which escapes the SDK's phone simulator entirely once it centers
// and scales the app into its own box — the overlay would darken the real
// browser viewport (including the simulator's side panels) and the content
// would anchor to the real window edge, nowhere near the phone. Passing the
// simulator's own screen element keeps every dialog visually trapped inside
// the phone, same reasoning as MobileBottomDrawer's own mount point.
// `undefined` outside the simulator falls back to Radix's own default,
// which is correct there (no separate "phone" box to contain within).
//
// Centered via `left-1/2 top-1/2` + translate (not viewport units): this
// resolves against the dialog's own CSS containing block, which inside the
// simulator is the phone screen itself (a transformed ancestor), not the
// real browser viewport — the same reasoning documented throughout this
// repo for why `vh`/`dvh`/`100vw` break inside the simulator. `max-h-[85%]`
// is a real, phone-accurate bound for the same reason.
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
