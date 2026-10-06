"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { AlertCircle } from "lucide-react";
import { createPatientAction, updatePatientAction, type PatientPayload } from "./patientActions";

const UF = [
  "AC", "AL", "AP", "AM", "BA", "CE", "DF", "ES", "GO", "MA", "MT", "MS", "MG", "PA", "PB",
  "PR", "PE", "PI", "RJ", "RN", "RS", "RO", "RR", "SC", "SP", "SE", "TO",
];

const EMPTY: PatientPayload = {
  given_name: "",
  family_name: "",
  birth_date: "",
  gender: "",
  identifier: "",
  cpf: "",
  cns: "",
  email: "",
  phone: "",
  cep: "",
  street: "",
  street_number: "",
  complement: "",
  district: "",
  city_name: "",
  state_code: "",
};

/** Only send what the user filled in, so blank inputs store NULL and not "". */
function filled(data: PatientPayload): PatientPayload {
  return Object.fromEntries(
    Object.entries(data).filter(([, v]) => v !== "" && v !== null && v !== undefined),
  ) as PatientPayload;
}

const label = "text-sm font-medium";
const input = "w-full rounded-lg border bg-background px-3 py-2 text-sm";

export function PatientForm({
  patientId,
  initial,
}: {
  patientId?: string;
  initial?: PatientPayload & { cpf_last4?: string | null };
}) {
  const t = useTranslations("PatientForm");
  const router = useRouter();
  const isEdit = !!patientId;

  const [form, setForm] = useState<PatientPayload>({
    ...EMPTY,
    ...(initial ?? {}),
    // The API never returns the CPF itself (only cpf_last4): start blank and
    // treat "filled in" as the trigger to replace it.
    cpf: "",
  });
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const set =
    (k: keyof PatientPayload) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
      setForm((f) => ({ ...f, [k]: e.target.value }));

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!form.given_name?.trim()) {
      setError(t("GivenNameRequired"));
      return;
    }
    const payload = filled(form);
    // Deliberately a plain async handler: pushing the route from inside a
    // startTransition left the form stuck on "Saving…" and the URL unchanged
    // even though the draft had already been created (verified in the backend).
    setPending(true);
    try {
      const res = isEdit
        ? await updatePatientAction(patientId as string, payload)
        : await createPatientAction(payload);
      if (res.error) {
        setError(res.error);
        return;
      }
      // Navigation only: router.refresh() right after push() aborts the
      // in-flight RSC fetch, so the URL never leaves the form page.
      router.push(`/patients/${res.id ?? patientId}`);
    } catch {
      setError(t("SaveError"));
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={onSubmit} className="space-y-5" data-testid="patient-form">
      {/* Identification */}
      <fieldset className="space-y-3 rounded-lg border bg-card p-4">
        <legend className="px-1 text-sm font-semibold">{t("SectionIdentification")}</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <label className={label}>{t("GivenName")}</label>
            <input
              required
              data-testid="patient-given-name"
              value={form.given_name}
              onChange={set("given_name")}
              className={input}
            />
          </div>
          <div className="space-y-1">
            <label className={label}>{t("FamilyName")}</label>
            <input
              data-testid="patient-family-name"
              value={form.family_name}
              onChange={set("family_name")}
              className={input}
            />
          </div>
          <div className="space-y-1">
            <label className={label}>{t("BirthDate")}</label>
            <input type="date" value={form.birth_date} onChange={set("birth_date")} className={input} />
          </div>
          <div className="space-y-1">
            <label className={label}>{t("Gender")}</label>
            <select value={form.gender} onChange={set("gender")} className={input}>
              <option value="">{t("GenderUnspecified")}</option>
              <option value="female">{t("Female")}</option>
              <option value="male">{t("Male")}</option>
              <option value="other">{t("Other")}</option>
            </select>
          </div>
          <div className="space-y-1">
            <label className={label}>{t("Cpf")}</label>
            <input
              inputMode="numeric"
              data-testid="patient-cpf"
              placeholder={isEdit && initial?.cpf_last4 ? t("CpfKeep", { last4: initial.cpf_last4 }) : ""}
              value={form.cpf}
              onChange={set("cpf")}
              className={input}
            />
            <p className="text-xs text-muted-foreground">{t("CpfHint")}</p>
          </div>
          <div className="space-y-1">
            <label className={label}>{t("Cns")}</label>
            <input
              inputMode="numeric"
              data-testid="patient-cns"
              value={form.cns}
              onChange={set("cns")}
              className={input}
            />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <label className={label}>{t("Identifier")}</label>
            <input value={form.identifier} onChange={set("identifier")} className={input} />
            <p className="text-xs text-muted-foreground">{t("IdentifierHint")}</p>
          </div>
        </div>
      </fieldset>

      {/* Contact */}
      <fieldset className="space-y-3 rounded-lg border bg-card p-4">
        <legend className="px-1 text-sm font-semibold">{t("SectionContact")}</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <label className={label}>{t("Email")}</label>
            <input type="email" value={form.email} onChange={set("email")} className={input} />
          </div>
          <div className="space-y-1">
            <label className={label}>{t("Phone")}</label>
            <input type="tel" value={form.phone} onChange={set("phone")} className={input} />
          </div>
        </div>
      </fieldset>

      {/* Address */}
      <fieldset className="space-y-3 rounded-lg border bg-card p-4">
        <legend className="px-1 text-sm font-semibold">{t("SectionAddress")}</legend>
        <div className="grid gap-3 sm:grid-cols-6">
          <div className="space-y-1 sm:col-span-2">
            <label className={label}>{t("Cep")}</label>
            <input
              inputMode="numeric"
              data-testid="patient-cep"
              value={form.cep}
              onChange={set("cep")}
              className={input}
            />
          </div>
          <div className="space-y-1 sm:col-span-3">
            <label className={label}>{t("Street")}</label>
            <input data-testid="patient-street" value={form.street} onChange={set("street")} className={input} />
          </div>
          <div className="space-y-1">
            <label className={label}>{t("Number")}</label>
            <input value={form.street_number} onChange={set("street_number")} className={input} />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <label className={label}>{t("Complement")}</label>
            <input value={form.complement} onChange={set("complement")} className={input} />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <label className={label}>{t("District")}</label>
            <input value={form.district} onChange={set("district")} className={input} />
          </div>
          <div className="space-y-1 sm:col-span-2">
            <label className={label}>{t("City")}</label>
            <input
              data-testid="patient-city"
              value={form.city_name}
              onChange={set("city_name")}
              className={input}
            />
          </div>
          <div className="space-y-1">
            <label className={label}>{t("State")}</label>
            <select data-testid="patient-state" value={form.state_code} onChange={set("state_code")} className={input}>
              <option value="">—</option>
              {UF.map((uf) => (
                <option key={uf} value={uf}>
                  {uf}
                </option>
              ))}
            </select>
          </div>
        </div>
      </fieldset>

      {error && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <AlertCircle className="size-4 shrink-0" />
          {error}
        </p>
      )}

      <button
        type="submit"
        disabled={pending}
        data-testid="patient-submit"
        className="rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
      >
        {pending ? t("Saving") : isEdit ? t("Save") : t("Create")}
      </button>
    </form>
  );
}