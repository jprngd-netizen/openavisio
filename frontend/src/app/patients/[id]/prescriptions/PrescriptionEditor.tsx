"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import {
  Plus,
  X,
  RefreshCw,
  AlertCircle,
  Loader2,
} from "lucide-react";
import {
  getPrescription,
  updatePrescription,
  retryPrescription,
} from "@/lib/api";

const DEBOUNCE_MS = 1500;

export function PrescriptionEditor({
  prescriptionId,
  isPrescriber,
}: {
  prescriptionId: string;
  isPrescriber: boolean;
}) {
  const router = useRouter();
  const t = useTranslations("Prescriptions");

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [notes, setNotes] = useState("");
  const [items, setItems] = useState<any[]>([]);
  const [version, setVersion] = useState(1);
  const [status, setStatus] = useState("draft");

  const [dirty, setDirty] = useState(false);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [conflict, setConflict] = useState<{ currentVersion: number } | null>(
    null,
  );
  const [retrying, setRetrying] = useState(false);

  // Mutable shadow refs for closures (useState vars are local consts)
  const _notesRef = useRef("");
  const _itemsRef = useRef<any[]>([]);
  const _versionRef = useRef(1);
  const _statusRef = useRef("draft");

  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Load prescription data on mount
  useEffect(() => {
    getPrescription(prescriptionId)
      .then((p: any) => {
        const loadedNotes = p.notes || "";
        const loadedItems =
          p.items?.map((item: any, i: number) => ({
            ...item,
            sort_order: item.sort_order ?? i,
          })) ?? [];
        _notesRef.current = loadedNotes;
        _itemsRef.current = loadedItems;
        _versionRef.current = p.version;
        _statusRef.current = p.status;
        setNotes(loadedNotes);
        setItems(loadedItems);
        setVersion(p.version);
        setStatus(p.status);
        setLoading(false);
      })
      .catch((e: Error) => {
        setError(e.message ?? "Failed to load prescription");
        setLoading(false);
      });
  }, [prescriptionId]);

  function scheduleAutosave() {
    if (_statusRef.current !== "draft") return;
    setDirty(true);
    setSaveError(null);
    setConflict(null);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(doAutosave, DEBOUNCE_MS);
  }

  async function doAutosave() {
    setSaving(true);
    try {
      const result = await updatePrescription(prescriptionId, {
        version: _versionRef.current,
        notes: _notesRef.current || null,
        items: _itemsRef.current.map((item, i) => ({
          medication_name: item.medication_name,
          posology: item.posology,
          quantity: item.quantity,
          sort_order: i,
        })),
      });
      if (result.ok) {
        _versionRef.current = result.data.version;
        setVersion(result.data.version);
        setDirty(false);
        setSaveError(null);
        setConflict(null);
      } else if (result.conflict) {
        setConflict({
          currentVersion: result.currentVersion ?? _versionRef.current + 1,
        });
      } else {
        setSaveError(result.error);
      }
    } catch (err: any) {
      setSaveError(String(err.message ?? err));
    } finally {
      setSaving(false);
    }
  }

  async function handleReload() {
    try {
      const current = await getPrescription(prescriptionId);
      _versionRef.current = current.version;
      setVersion(current.version);
      setConflict(null);
      setSaveError(null);
    } catch {
      setSaveError("Failed to reload");
    }
  }

  async function handleRetry() {
    setRetrying(true);
    try {
      await retryPrescription(prescriptionId);
      router.refresh();
    } catch (err: any) {
      setSaveError(err.message ?? "Retry failed");
    } finally {
      setRetrying(false);
    }
  }

  function addItem() {
    const updated = [
      ..._itemsRef.current,
      {
        medication_name: "",
        posology: "",
        quantity: "",
        sort_order: _itemsRef.current.length,
      },
    ];
    _itemsRef.current = updated;
    setItems(updated);
    scheduleAutosave();
  }

  function removeItem(index: number) {
    const updated = _itemsRef.current.filter((_, i) => i !== index);
    _itemsRef.current = updated;
    setItems(updated);
    scheduleAutosave();
  }

  function updateItem(index: number, field: string, value: string) {
    const updated = [..._itemsRef.current];
    updated[index] = { ...updated[index], [field]: value };
    _itemsRef.current = updated;
    setItems(updated);
    scheduleAutosave();
  }

  function handleNotesChange(value: string) {
    _notesRef.current = value;
    setNotes(value);
    scheduleAutosave();
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center gap-2 py-8 text-muted-foreground">
        <Loader2 className="size-4 animate-spin" />
        {t("Loading")}
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
        {error}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Conflict banner */}
      {conflict && (
        <div
          className="flex items-center gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3 text-sm dark:border-amber-900/30 dark:bg-amber-900/10"
          data-testid="conflict-banner"
        >
          <AlertCircle className="size-4 shrink-0 text-amber-600" />
          <span className="flex-1">{t("ConflictMessage")}</span>
          <button
            onClick={handleReload}
            className="inline-flex items-center gap-1.5 rounded-md bg-amber-100 px-3 py-1.5 text-xs font-medium text-amber-800 hover:bg-amber-200 dark:bg-amber-900/30 dark:text-amber-300"
          >
            <RefreshCw className="size-3.5" />
            {t("Reload")}
          </button>
        </div>
      )}

      {/* Save error (non-conflict) */}
      {saveError && !conflict && (
        <div className="rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          {saveError}
        </div>
      )}

      {/* Failed status → retry banner */}
      {status === "failed" && (
        <div className="flex items-center gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm dark:border-red-900/30 dark:bg-red-900/10">
          <AlertCircle className="size-4 shrink-0 text-red-600" />
          <span className="flex-1">{t("FailedMessage")}</span>
          <button
            onClick={handleRetry}
            disabled={retrying}
            className="inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium text-orange-600 hover:bg-orange-50 disabled:opacity-50 transition-colors dark:hover:bg-orange-950/20"
          >
            <RefreshCw
              className={`size-3.5 ${retrying ? "animate-spin" : ""}`}
            />
            {retrying ? t("Retrying") : t("Retry")}
          </button>
        </div>
      )}

      {/* Header with save indicator */}
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">{t("EditorTitle")}</h3>
        <span
          className="text-xs text-muted-foreground"
          data-testid="save-indicator"
        >
          {saving
            ? t("Saving")
            : dirty
              ? t("Unsaved")
              : t("Saved")}
        </span>
      </div>

      {/* Notes */}
      <div>
        <label className="block mb-1 text-sm font-medium">{t("Notes")}</label>
        <textarea
          value={notes}
          onChange={(e) => handleNotesChange(e.target.value)}
          className="w-full rounded-lg border bg-card px-3 py-2 text-sm"
          rows={3}
          disabled={status !== "draft"}
          data-testid="editor-notes"
        />
      </div>

      {/* Items */}
      <div>
        <div className="mb-2 flex items-center justify-between">
          <label className="text-sm font-medium">{t("Items")}</label>
          {status === "draft" && (
            <button
              onClick={addItem}
              className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs font-medium text-primary hover:bg-primary/10"
              data-testid="add-item"
            >
              <Plus className="size-3.5" />
              {t("AddItem")}
            </button>
          )}
        </div>

        {items.length === 0 ? (
          <p className="py-2 text-xs text-muted-foreground">{t("NoItems")}</p>
        ) : (
          <div className="space-y-2">
            {items.map((item, i) => (
              <div
                key={i}
                className="flex items-start gap-2 rounded-lg border bg-card p-3"
              >
                <div className="grid flex-1 grid-cols-3 gap-2">
                  <input
                    value={item.medication_name}
                    onChange={(e) =>
                      updateItem(i, "medication_name", e.target.value)
                    }
                    placeholder={t("Medication")}
                    className="rounded-md border bg-card px-2 py-1.5 text-xs"
                    disabled={status !== "draft"}
                    data-testid={`item-name-${i}`}
                  />
                  <input
                    value={item.posology}
                    onChange={(e) =>
                      updateItem(i, "posology", e.target.value)
                    }
                    placeholder={t("Posology")}
                    className="rounded-md border bg-card px-2 py-1.5 text-xs"
                    disabled={status !== "draft"}
                    data-testid={`item-posology-${i}`}
                  />
                  <input
                    value={item.quantity}
                    onChange={(e) =>
                      updateItem(i, "quantity", e.target.value)
                    }
                    placeholder={t("Quantity")}
                    className="rounded-md border bg-card px-2 py-1.5 text-xs"
                    disabled={status !== "draft"}
                    data-testid={`item-quantity-${i}`}
                  />
                </div>
                {status === "draft" && (
                  <button
                    onClick={() => removeItem(i)}
                    className="p-1 text-muted-foreground hover:text-destructive transition-colors"
                    data-testid={`remove-item-${i}`}
                  >
                    <X className="size-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Issue status */}
      <div className="flex items-center gap-3 pt-2">
        {isPrescriber ? (
          <span
            className="text-xs text-muted-foreground"
            data-testid="issue-status"
          >
            {t("ReadyToIssue")}
          </span>
        ) : (
          <span
            className="flex items-center gap-2 text-xs text-muted-foreground"
            data-testid="issue-status"
          >
            <AlertCircle className="size-3.5" />
            {t("NotPrescriber")}
          </span>
        )}
      </div>
    </div>
  );
}