import { ConfirmModal } from "@app/components/modals/ConfirmModal";

export interface ExitConfirmModalProps {
  open: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ExitConfirmModal({
  onCancel,
  onConfirm,
  open,
}: ExitConfirmModalProps) {
  return (
    <ConfirmModal
      confirmLabel="Leave"
      description="You will return to the Up app."
      destructive
      onCancel={onCancel}
      onConfirm={onConfirm}
      open={open}
      title="Leave this mini-app?"
    />
  );
}
