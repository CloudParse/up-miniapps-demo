import {
  Banner,
  Button,
  isApiError,
  LoadingState,
  SectionHeader,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableEmpty,
  TableHead,
  TableHeaderCell,
  TableRow,
} from "@cloudparse/up-backoffice-sdk";
import { NoteModal } from "@plugin/features/demo/NoteModal";
import type { DemoNote } from "@plugin/features/demo/types";
import { demoService } from "@plugin/services/demo";
import { Plus, StickyNote } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

function isNotServed(error: unknown): boolean {
  // isApiError, never instanceof: the error class comes from the host's copy of the SDK.
  return isApiError(error) && error.status === 404;
}

function describe(error: unknown): string {
  if (!isApiError(error)) return "Unexpected error.";
  if (error.status === 403) {
    return "The API refuses this account: it needs the mini-app administrator scope.";
  }
  return `The API answered ${error.status}: ${error.message}`;
}

// The usual job of a plugin: the admins put data into the mini-app's database through an admin route.
export function NotesPage() {
  const [notes, setNotes] = useState<DemoNote[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [notServed, setNotServed] = useState(false);

  const load = useCallback(async () => {
    setError(null);
    try {
      setNotes(await demoService.listNotes());
    } catch (caught) {
      if (isNotServed(caught)) setNotServed(true);
      else setError(describe(caught));
      setNotes([]);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // min-h-96: the Studio frame is as tall as the page, and the modal is fixed inside it. A short page
  // (a few notes) would cut the "New note" modal.
  return (
    <div className="min-h-96 space-y-6">
      {notServed && (
        <Banner
          message="The demo routes are not served in production: the API answers 404. Replace this page and the routes /admin/demo/* with your own."
          variant="warning"
        />
      )}
      {error && (
        <Banner
          message={error}
          onClose={() => setError(null)}
          variant="error"
        />
      )}
      <SectionHeader
        actions={
          <Button
            disabled={notServed}
            onClick={() => setCreating(true)}
            type="button"
          >
            <Plus className="size-4" />
            New note
          </Button>
        }
        description="Each note is a row of the database, written by the API's admin route."
        title="Notes"
      />
      {notServed ? null : notes === null ? (
        <LoadingState />
      ) : (
        <TableContainer>
          <Table>
            <TableHead>
              <tr>
                <TableHeaderCell>Text</TableHeaderCell>
                <TableHeaderCell align="right">Written</TableHeaderCell>
              </tr>
            </TableHead>
            <TableBody>
              {notes.length === 0 ? (
                <TableEmpty
                  colSpan={2}
                  description="Write the first one with the button above."
                  icon={StickyNote}
                  title="No notes yet"
                />
              ) : (
                notes.map((note) => (
                  <TableRow key={note.id}>
                    <TableCell className="font-extrabold">
                      {note.text}
                    </TableCell>
                    <TableCell align="right" className="text-muted-foreground">
                      {new Date(note.createdAt).toLocaleString()}
                    </TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </TableContainer>
      )}
      {creating && (
        <NoteModal
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false);
            load();
          }}
        />
      )}
    </div>
  );
}
