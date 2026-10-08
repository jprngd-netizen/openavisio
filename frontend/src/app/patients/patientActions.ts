"use server";

import { auth } from "@/auth";

const API = process.env.API_URL || "http://localhost:8000";

export type PatientPayload = {
  given_name?: string;
  family_name?: string;
  birth_date?: string;
  gender?: string;
  identifier?: string;
  cpf?: string;
  cns?: string;
  email?: string;
  phone?: string;
  cep?: string;
  street?: string;
  street_number?: string;
  complement?: string;
  district?: string;
  city_name?: string;
  state_code?: string;
  // Employment context (occupational record cover)
  registration?: string;
  company?: string;
  contract?: string;
  job_title?: string;
  admission_date?: string;
  cost_center?: string;
  work_location?: string;
  shift?: string;
};

async function getToken(): Promise<string | undefined> {
  const session = await auth();
  return (session as any)?.accessToken as string | undefined;
}

async function failure(res: Response, verb: string): Promise<string> {
  const detail = await res.json().catch(() => ({}));
  const d = (detail as any)?.detail;
  if (typeof d === "string") return d;
  if (Array.isArray(d) && d[0]?.msg) return String(d[0].msg);
  return `Failed to ${verb} patient (${res.status}).`;
}

export async function createPatientAction(data: PatientPayload): Promise<{ id?: string; error?: string }> {
  const token = await getToken();
  if (!token) return { error: "Not authenticated." };

  const res = await fetch(`${API}/api/patients`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });
  if (!res.ok) return { error: await failure(res, "create") };

  const patient = await res.json();
  return { id: patient.id };
}

export async function updatePatientAction(
  id: string,
  data: PatientPayload,
): Promise<{ id?: string; error?: string }> {
  const token = await getToken();
  if (!token) return { error: "Not authenticated." };

  const res = await fetch(`${API}/api/patients/${id}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify(data),
  });
  if (!res.ok) return { error: await failure(res, "update") };

  return { id };
}

/**
 * Reveal the full CPF (normally only cpf_last4 is exposed). Deliberate,
 * auditable action: the backend writes an audit-log entry on every call.
 */
export async function revealPatientCpfAction(id: string): Promise<{ cpf?: string; error?: string }> {
  const token = await getToken();
  if (!token) return { error: "Not authenticated." };

  const res = await fetch(`${API}/api/patients/${id}/cpf`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) return { error: await failure(res, "reveal CPF for") };
  const data = await res.json();
  return { cpf: data.cpf };
}