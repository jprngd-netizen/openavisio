"use client";

import { useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import {
  Cake,
  Eye,
  EyeOff,
  IdCard,
  Mars,
  Pencil,
  User as UserIcon,
  Venus,
} from "lucide-react";
import { PatientAvatar } from "@/components/PatientAvatar";
import { formatDate, ageFromBirthDate } from "@/lib/utils";
import { revealPatientCpfAction } from "@/app/patients/patientActions";

// "Capa do Prontuário" — the front page of the clinical chart. Identity (A) and
// the record header (C) are read from the patient/organization; nothing is
// duplicated: the patient fields are the single source, edited in the patient
// form. The CPF is masked and only revealed on an explicit, audited request.

const label = "text-[11px] uppercase tracking-wide text-muted-foreground";
const value = "text-sm font-medium";

function Field({ labelText, children }: { labelText: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <div className={label}>{labelText}</div>
      {children}
    </div>
  );
}

export function CoverView({
  patientId,
  patient,
  organizationName,
  recordNumber,
}: {
  patientId: string;
  patient: any;
  organizationName: string | null;
  recordNumber: string;
}) {
  const t = useTranslations("Cover");
  const tp = useTranslations("Patient");
  const locale = useLocale();

  const age = ageFromBirthDate(patient.birth_date);
  const genderLabel = patient.gender
    ? ({ male: tp("Male"), female: tp("Female"), other: tp("Other") } as Record<string, string>)[
        String(patient.gender).toLowerCase()
      ] ?? patient.gender
    : null;
  const GenderIcon =
    String(patient.gender).toLowerCase() === "female"
      ? Venus
      : String(patient.gender).toLowerCase() === "male"
        ? Mars
        : UserIcon;

  const none = t("None");

  // --- CPF: masked by default, full value on explicit, audited request ------
  const [cpf, setCpf] = useState<string | null>(null);
  const [cpfError, setCpfError] = useState<string | null>(null);
  const [cpfPending, setCpfPending] = useState(false);

  async function toggleCpf() {
    if (cpf) {
      setCpf(null);
      return;
    }
    setCpfError(null);
    setCpfPending(true);
    try {
      const res = await revealPatientCpfAction(patientId);
      if (res.error) setCpfError(t("CpfError"));
      else setCpf(res.cpf ?? null);
    } catch {
      setCpfError(t("CpfError"));
    } finally {
      setCpfPending(false);
    }
  }

  const maskedCpf = patient.cpf_last4 ? `•••.•••.•••-${patient.cpf_last4}` : none;

  return (
    <div className="space-y-6">
      {/* (A) Identificação do paciente */}
      <section className="rounded-2xl border bg-card p-5">
        <h2 className="mb-4 text-sm font-semibold">{t("GroupWorker")}</h2>
        <div className="flex flex-col gap-5 sm:flex-row">
          <PatientAvatar
            givenName={patient.given_name}
            familyName={patient.family_name}
            photoUrl={patient.has_photo ? `/api/patients/${patientId}/photo` : undefined}
            className="size-24 text-2xl"
          />
          <div className="flex-1 space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <div className={label}>{t("FullName")}</div>
                <div className="text-lg font-semibold leading-tight">
                  {patient.given_name} {patient.family_name}
                </div>
              </div>
              <Link
                href={`/patients/${patientId}/edit`}
                className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium text-muted-foreground hover:text-foreground"
              >
                <Pencil className="size-3.5" />
                {t("EditPatient")}
              </Link>
            </div>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              <Field labelText={t("BirthDate")}>
                <div className={`${value} flex items-center gap-1.5`}>
                  <Cake className="size-4 text-muted-foreground" />
                  {patient.birth_date ? formatDate(patient.birth_date, locale) : none}
                  {age !== null && <span className="text-muted-foreground">· {tp("Age", { count: age })}</span>}
                </div>
              </Field>
              <Field labelText={t("Gender")}>
                <div className={`${value} flex items-center gap-1.5`}>
                  <GenderIcon className="size-4 text-muted-foreground" />
                  {genderLabel ?? none}
                </div>
              </Field>
              <Field labelText={t("PatientId")}>
                <div className={`${value} flex items-center gap-1.5`}>
                  <IdCard className="size-4 text-muted-foreground" />
                  {patient.identifier || none}
                </div>
              </Field>
              <Field labelText={t("Cpf")}>
                <div className="flex items-center gap-2">
                  <span className={`${value} font-mono`}>{cpf ?? maskedCpf}</span>
                  {patient.cpf_last4 && (
                    <button
                      type="button"
                      onClick={toggleCpf}
                      disabled={cpfPending}
                      className="inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground disabled:opacity-50"
                    >
                      {cpf ? <EyeOff className="size-3.5" /> : <Eye className="size-3.5" />}
                      {cpf ? t("HideCpf") : t("ShowCpf")}
                    </button>
                  )}
                </div>
                {cpfError && <p className="text-xs text-destructive">{cpfError}</p>}
              </Field>
              <Field labelText={t("Cns")}>
                <div className={`${value} font-mono`}>{patient.cns || none}</div>
              </Field>
            </div>
          </div>
        </div>
      </section>

      {/* (C) Cabeçalho do prontuário */}
      <section className="rounded-2xl border bg-card p-5">
        <h2 className="mb-4 text-sm font-semibold">{t("GroupHeader")}</h2>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field labelText={t("RecordNumber")}>
            <div className={`${value} font-mono`}>{recordNumber}</div>
          </Field>
          <Field labelText={t("IssuedAt")}>
            <div className={value}>{formatDate(new Date().toISOString().slice(0, 10), locale)}</div>
          </Field>
          <Field labelText={t("Organization")}>
            <div className={value}>{organizationName || none}</div>
          </Field>
        </div>
      </section>
    </div>
  );
}
