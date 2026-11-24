import {
  Banner,
  Input,
  isApiError,
  Modal,
  ModalActions,
} from "@cloudparse/up-backoffice-sdk";
import { demoService } from "@plugin/services/demo";
import { StickyNote } from "lucide-react";
import { useState } from "react";

const MAX_LENGTH = 200;

interface NoteModalProps {
  onClose: () => void;
  onSaved: () => void;
}

// The form of the plugin. No <form> element: the Studio runs the plugin in an iframe sandboxed without
// allow-forms, so a form submission would be blocked. The button calls handleSubmit instead.
export function NoteModal({ onClose, onSaved }: NoteModalProps) {
  const [text, setText] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (!text.trim()) return;
    setSaving(true);
    setError(null);
    try {
      await demoService.addNote(text);
      onSaved();
    } catch (caught) {
      setError(
        isApiError(caught)
          ? `The API answered ${caught.status}: ${caught.message}`
          : "Unexpected error.",
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal
      description="The API writes it in the demo_notes table of the mini-app's database."
      dismissible={!saving}
      icon={StickyNote}
      onClose={onClose}
      title="New note"
    >
      {error && <Banner message={error} variant="error" />}
      <Input
        label="Text"
        maxLength={MAX_LENGTH}
        onChange={(e) => setText(e.target.value)}
        placeholder="e.g. The bar opens at 8 pm"
        value={text}
      />
      <ModalActions
        isSubmitting={saving}
        onCancel={onClose}
        onSubmit={handleSubmit}
        submitDisabled={!text.trim()}
        submitLabel="Save"
        submitType="button"
      />
    </Modal>
  );
}
