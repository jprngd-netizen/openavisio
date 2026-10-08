"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import Link from "next/link";
import {
  AlertCircle,
  Cake,
  Eye,
  EyeOff,
  IdCard,
  Mars,
  Pencil,
  Save,
  User as UserIcon,
  Venus,
} from "lucide-react";
import { PatientAvatar } from "@/components/PatientAvatar";
import { formatDate, ageFromBirthDate } from "@/lib/utils";
import { updatePatientAction, revealPatientCpfAction, type PatientPayload } from "@/app/patients/patientActions";

// "Capa do Prontuário" — section #1 of the occupational record. Identity (A)
// and the record header (C) are read from the patient/organization; only the
// employment block (B) is editable here. Nothing is duplicated: the patient
// fields are the single source and are edited in the patient form.

const label = "text-[11px] uppercase tracking-wide text-muted-foreground";
const value = "text-sm font-medium";
const input = "w-full rounded-lg border bg-background px-3 py-2 text-sm";

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
  const t = useTranslations("OccupationalCover");
  const tp = useTranslations("Patient");
  const locale = useLocale();
  const router = useRouter();

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

  // --- Employment block (B): editable, real integration --------------------
  const [form, setForm] = useState<PatientPayload>({
    registration: patient.registration ?? "",
    company: patient.company ?? "",
    contract: patient.contract ?? "",
    job_title: patient.job_title ?? "",
    admission_date: patient.admission_date ?? "",
    cost_center: patient.cost_center ?? "",
    work_location: patient.work_location ?? "",
    shift: patient.shift ?? "",
  });
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const [pending, setPending] = useState(false);

  const set =
    (k: keyof PatientPayload) =>
    (e: React.ChangeEvent<HTMLInputElement>) =>
      setForm((f) => ({ ...f, [k]: e.target.value }));

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setSaved(false);
    // Only send filled values (blank = leave unchanged), matching PatientForm.
    const payload = Object.fromEntries(
      Object.entries(form).filter(([, v]) => v !== "" && v !== null && v !== undefined),
    ) as PatientPayload;
    setPending(true);
    try {
      const res = await updatePatientAction(patientId, payload);
      if (res.error) {
        setError(res.error);
        return;
      }
      setSaved(true);
      router.refresh();
    } catch {
      setError(t("SaveError"));
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* (A) Identificação do trabalhador */}
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

      {/* (B) Vínculo empregatício & lotação — editable */}
      <form onSubmit={onSubmit} className="rounded-2xl border bg-card p-5">
        <h2 className="mb-4 text-sm font-semibold">{t("GroupEmployment")}</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <div className="space-y-1">
            <label className={label}>{t("Registration")}</label>
            <input value={form.registration} onChange={set("registration")} className={input} />
          </div>
          <div className="space-y-1">
            <label className={label}>{t("Company")}</label>
            <input value={form.company} onChange={set("company")} className={input} />
          </div>
          <div className="space-y-1">
            <label className={label}>{t("Contract")}</label>
            <input value={form.contract} onChange={set("contract")} className={input} />
          </div>
          <div className="space-y-1">
            <label className={label}>{t("JobTitle")}</label>
            <input value={form.job_title} onChange={set("job_title")} className={input} />
          </div>
          <div className="space-y-1">
            <label className={label}>{t("AdmissionDate")}</label>
            <input type="date" value={form.admission_date} onChange={set("admission_date")} className={input} />
          </div>
          <div className="space-y-1">
            <label className={label}>{t("Shift")}</label>
            <input value={form.shift} onChange={set("shift")} className={input} />
          </div>
          <div className="space-y-1">
            <label className={label}>{t("CostCenter")}</label>
            <input value={form.cost_center} onChange={set("cost_center")} className={input} />
          </div>
          <div className="space-y-1">
            <label className={label}>{t("WorkLocation")}</label>
            <input value={form.work_location} onChange={set("work_location")} className={input} />
          </div>
        </div>

        {error && (
          <p className="mt-3 flex items-center gap-1.5 text-sm text-destructive">
            <AlertCircle className="size-4 shrink-0" />
            {error}
          </p>
        )}
        {saved && !error && <p className="mt-3 text-sm text-emerald-600 dark:text-emerald-400">{t("Saved")}</p>}

        <button
          type="submit"
          disabled={pending}
          className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-primary px-4 py-2 text-sm font-medium text-primary-foreground disabled:opacity-50"
        >
          <Save className="size-4" />
          {pending ? t("Saving") : t("Save")}
        </button>
      </form>

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
