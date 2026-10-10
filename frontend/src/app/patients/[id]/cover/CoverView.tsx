"use client";

import { useState } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import {
  AlertTriangle,
  Cake,
  ChevronRight,
  ClipboardList,
  Eye,
  EyeOff,
  IdCard,
  Mars,
  Pencil,
  Pill,
  ShieldAlert,
  User as UserIcon,
  Venus,
  type LucideIcon,
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

// One clinical-safety block: a link to its section that lists the active items
// (or a discreet empty state). `alert` switches the allergy block to the
// destructive palette so a recorded allergy reads as a warning at a glance.
function SafetyBlock({
  href,
  Icon,
  title,
  emptyLabel,
  viewLabel,
  items,
  renderItem,
  alert = false,
}: {
  href: string;
  Icon: LucideIcon;
  title: string;
  emptyLabel: string;
  viewLabel: string;
  items: any[];
  renderItem: (item: any) => React.ReactNode;
  alert?: boolean;
}) {
  return (
    <Link
      href={href}
      className={`group flex flex-col rounded-xl border p-4 transition-colors ${
        alert
          ? "border-destructive/40 bg-destructive/[0.06] hover:bg-destructive/[0.1]"
          : "bg-card hover:bg-accent"
      }`}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <div
          className={`flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide ${
            alert ? "text-destructive" : "text-muted-foreground"
          }`}
        >
          <Icon className="size-3.5" />
          {title}
        </div>
        <ChevronRight className="size-4 text-muted-foreground transition-transform group-hover:translate-x-0.5" />
      </div>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{emptyLabel}</p>
      ) : (
        <ul className="space-y-1">
          {items.map((item) => (
            <li
              key={item.id}
              className={`truncate text-sm ${alert ? "font-medium" : ""}`}
              title={String(item.substance_display ?? item.medication_display ?? item.code_display ?? "")}
            >
              {renderItem(item)}
            </li>
          ))}
        </ul>
      )}
      <span className="mt-auto pt-2 text-xs text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100">
        {viewLabel}
      </span>
    </Link>
  );
}

export function CoverView({
  patientId,
  patient,
  organizationName,
  recordNumber,
  safety,
}: {
  patientId: string;
  patient: any;
  organizationName: string | null;
  recordNumber: string;
  safety: { allergies: any[]; medications: any[]; conditions: any[] };
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
      {/* (B) Banner de segurança clínica (WS-9) — alergias, medicações ativas
          e problemas ativos do paciente, agregados numa única leitura. A
          alergia é o bloco de alerta: cor destrutiva quando há registro. */}
      <section
        aria-label={t("SafetyTitle")}
        className="rounded-2xl border border-destructive/30 bg-destructive/[0.04] p-5"
      >
        <div className="mb-4 flex items-center gap-2">
          <ShieldAlert className="size-4 text-destructive" />
          <h2 className="text-sm font-semibold">{t("SafetyTitle")}</h2>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <SafetyBlock
            href={`/patients/${patientId}/antecedents`}
            Icon={AlertTriangle}
            title={t("SafetyAllergies")}
            emptyLabel={t("SafetyNoAllergies")}
            viewLabel={t("SafetyView")}
            items={safety.allergies}
            alert
            renderItem={(a: any) => (
              <>
                {a.substance_display}
                {a.severity && (
                  <span className="ml-1 text-xs font-normal text-destructive/80">{a.severity}</span>
                )}
              </>
            )}
          />
          <SafetyBlock
            href={`/patients/${patientId}/medications`}
            Icon={Pill}
            title={t("SafetyMedications")}
            emptyLabel={t("SafetyNoMedications")}
            viewLabel={t("SafetyView")}
            items={safety.medications}
            renderItem={(m: any) => (
              <>
                {m.medication_display}
                {m.dosage_text && (
                  <span className="ml-1 text-xs font-normal text-muted-foreground">{m.dosage_text}</span>
                )}
              </>
            )}
          />
          <SafetyBlock
            href={`/patients/${patientId}/conditions`}
            Icon={ClipboardList}
            title={t("SafetyConditions")}
            emptyLabel={t("SafetyNoConditions")}
            viewLabel={t("SafetyView")}
            items={safety.conditions}
            renderItem={(c: any) => (
              <>
                {c.code_display}
                {c.code && <span className="ml-1 font-mono text-xs font-normal text-muted-foreground">{c.code}</span>}
              </>
            )}
          />
        </div>
      </section>

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
