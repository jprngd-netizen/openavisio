"use server";

import { revalidatePath } from "next/cache";
import { auth } from "@/auth";
import { getTranslations } from "next-intl/server";

const API = process.env.API_URL || "http://localhost:8000";

export async function updatePrescriberAction(fields: {
  given_name: string;
  family_name: string;
  cpf?: string | null;
  birth_date?: string | null;
  board_code?: string | null;
  board_number?: string | null;
  board_state?: string | null;
  email?: string | null;
  phone?: string | null;
  sex?: string | null;
  city_id?: number | null;
  specialty_id?: number | null;
  user_id?: string | null;
}): Promise<{ error?: string; data?: any }> {
  const t = await getTranslations("Admin");
  const session = await auth();
  const token = (session as any)?.accessToken;
  if (!token) return { error: t("NotAuthenticated") };

  const body: Record<string, any> = {
    given_name: fields.given_name,
    family_name: fields.family_name,
  };

  // Only send non-null fields — the backend preserves omitted values on update
  if (fields.cpf !== undefined) body.cpf = fields.cpf || null;
  if (fields.birth_date !== undefined) body.birth_date = fields.birth_date || null;
  if (fields.board_code !== undefined) body.board_code = fields.board_code || null;
  if (fields.board_number !== undefined) body.board_number = fields.board_number || null;
  if (fields.board_state !== undefined) body.board_state = fields.board_state || null;
  if (fields.email !== undefined) body.email = fields.email || null;
  if (fields.phone !== undefined) body.phone = fields.phone || null;
  if (fields.sex !== undefined) body.sex = fields.sex || null;
  if (fields.city_id !== undefined) body.city_id = fields.city_id;
  if (fields.specialty_id !== undefined) body.specialty_id = fields.specialty_id;
  if (fields.user_id !== undefined) body.user_id = fields.user_id || null;

  const res = await fetch(`${API}/api/admin/prescriber`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(body),
  });

  if (!res.ok) {
    const data = await res.json().catch(() => ({}));
    return { error: data.detail || t("FailedToSavePrescriber") };
  }

  revalidatePath("/admin/prescriber");
  return { data: await res.json() };
}