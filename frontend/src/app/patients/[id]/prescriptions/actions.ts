"use server";

import { redirect } from "next/navigation";
import { createPrescription } from "@/lib/api";

/**
 * Cria um rascunho de receita para o paciente e abre o editor.
 *
 * Criar o rascunho é o passo que faltava no fluxo: a página só renderiza o
 * editor quando existe um id (`?rx=<id>`), e nada na interface criava esse id.
 *
 * `redirect()` funciona lançando NEXT_REDIRECT, então NÃO pode ficar dentro do
 * try/catch — o catch engoliria o redirect.
 */
export async function createPrescriptionAction(formData: FormData): Promise<void> {
  const patientId = String(formData.get("patientId") ?? "").trim();
  if (!patientId) return;

  let createdId: string | null = null;
  let reason: "no_prescriber" | "error" = "error";

  try {
    const rx = await createPrescription(patientId);
    createdId = rx?.id ?? null;
  } catch (e) {
    // 409 = nenhum prescritor configurado (backend _get_prescriber_or_409).
    const message = e instanceof Error ? e.message : String(e);
    reason = /API error 409/.test(message) ? "no_prescriber" : "error";
  }

  if (createdId) {
    redirect(`/patients/${patientId}/prescriptions?rx=${createdId}`);
  }
  redirect(`/patients/${patientId}/prescriptions?error=${reason}`);
}
