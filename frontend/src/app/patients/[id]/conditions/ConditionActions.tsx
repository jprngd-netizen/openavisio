"use client";

import { useTransition, useState } from "react";
import { useRouter } from "next/navigation";
import { updateCondition, deleteCondition } from "@/lib/api";
import { Archive, Trash2, Undo2 } from "lucide-react";

export function ConditionActions({ id, status, iconBar = false, extra }: { id: string; status: string; iconBar?: boolean; extra?: React.ReactNode }) {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [confirmDelete, setConfirmDelete] = useState(false);

  function markObsolete() {
    startTransition(async () => {
      await updateCondition(id, { clinical_status: "inactive" });
      router.refresh();
    });
  }

  function markActive() {
    startTransition(async () => {
      await updateCondition(id, { clinical_status: "active" });
      router.refresh();
    });
  }

  function handleDelete() {
    if (!confirmDelete) { setConfirmDelete(true); return; }
    startTransition(async () => {
      await deleteCondition(id);
      router.refresh();
    });
  }

  // Phone: the same icon bar the documents list reveals on tap — one look everywhere.
  if (iconBar) {
    return (
      <div className="flex items-stretch divide-x border-t [&>*]:min-h-12 [&>*]:flex-1 [&>*]:justify-center [&>*]:rounded-none [&>*]:border-0">
        {extra}
        {status === "active" ? (
          <button onClick={markObsolete} disabled={pending} aria-label="Mark as obsolete"
                  className="inline-flex items-center text-foreground disabled:opacity-50">
            <Archive className="h-5 w-5" />
          </button>
        ) : (
          <button onClick={markActive} disabled={pending} aria-label="Mark as active"
                  className="inline-flex items-center bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 disabled:opacity-50">
            <Undo2 className="h-5 w-5" />
          </button>
        )}
        <button onClick={handleDelete} disabled={pending}
                aria-label={confirmDelete ? "Tap again to confirm" : "Delete"}
                className={`inline-flex items-center disabled:opacity-50 ${
                  confirmDelete ? "bg-destructive text-destructive-foreground" : "text-destructive"
                }`}>
          <Trash2 className="h-5 w-5" />
          {confirmDelete && <span className="ml-1.5 text-xs font-medium">Confirm</span>}
        </button>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2" onMouseLeave={() => setConfirmDelete(false)}>
      {status === "active" ? (
        <button
          onClick={markObsolete}
          disabled={pending}
          title="Mark as obsolete"
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted px-2.5 py-1 text-xs font-medium text-foreground hover:bg-muted/70 disabled:opacity-50 transition-colors"
        >
          <Archive className="h-3.5 w-3.5" />
          Obsolete
        </button>
      ) : (
        <button
          onClick={markActive}
          disabled={pending}
          title="Mark as active"
          className="inline-flex items-center gap-1.5 rounded-md border border-border bg-muted px-2.5 py-1 text-xs font-medium text-foreground hover:bg-muted/70 disabled:opacity-50 transition-colors"
        >
          <Undo2 className="h-3.5 w-3.5" />
          Reactivate
        </button>
      )}
      <button
        onClick={handleDelete}
        disabled={pending}
        title={confirmDelete ? "Click again to confirm" : "Delete"}
        className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs font-medium transition-colors disabled:opacity-50 ${
          confirmDelete
            ? "border-destructive bg-destructive text-destructive-foreground hover:bg-destructive/90"
            : "border-border bg-muted text-foreground hover:border-destructive hover:bg-destructive/10 hover:text-destructive"
        }`}
      >
        <Trash2 className="h-3.5 w-3.5" />
        {confirmDelete ? "Confirm" : "Delete"}
      </button>
    </div>
  );
}
