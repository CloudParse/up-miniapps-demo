import { Button } from "@app/components/ui/button";
import { Dialog } from "@app/components/ui/dialog";

export interface ConfirmModalProps {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel: string;
  cancelLabel?: string;
  destructive?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

// Generic confirmation. Specific flows wrap it (ExitConfirmModal) rather than
// re-implementing the markup.
export function ConfirmModal({
  cancelLabel = "Annuler",
  confirmLabel,
  description,
  destructive = false,
  onCancel,
  onConfirm,
  open,
  title,
}: ConfirmModalProps) {
  return (
    <Dialog
      description={description}
      onOpenChange={(next) => {
        if (!next) onCancel();
      }}
      open={open}
      title={title}
    >
      <Button onClick={onConfirm} variant={destructive ? "danger" : "primary"}>
        {confirmLabel}
      </Button>
      <Button onClick={onCancel} variant="secondary">
        {cancelLabel}
      </Button>
    </Dialog>
  );
}
