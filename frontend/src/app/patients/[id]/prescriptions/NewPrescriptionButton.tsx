"use client";

import { useFormStatus } from "react-dom";
import { useTranslations } from "next-intl";
import { FilePlus2, Loader2 } from "lucide-react";

/**
 * Botão de submit do form de criação. Precisa ser client só por causa do
 * `useFormStatus` (estado "criando…" + evita duplo-clique criar dois rascunhos).
 */
export function NewPrescriptionButton() {
  const t = useTranslations("Prescriptions");
  const { pending } = useFormStatus();

  return (
    <button
      type="submit"
      disabled={pending}
      data-testid="new-prescription"
      className="inline-flex items-center gap-2 rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground transition-opacity hover:opacity-90 disabled:opacity-60"
    >
      {pending ? <Loader2 className="size-4 animate-spin" /> : <FilePlus2 className="size-4" />}
      {t("New")}
    </button>
  );
}
