"use client";

import { useTranslations } from "next-intl";
import { listToChips, EDEMA_CLASS_KEY } from "./fexeoModel";

// Read-only projections of the FExEO-SUS structured fields, shown on the
// episode card and the visit rows. Only fields that were actually set are
// rendered; an episode/visit without FExEO data renders nothing.

// next-intl throws on a missing key; OCR-sourced enum values may be
// out-of-vocabulary, so never let a label lookup crash the chart.
function safeLabel(t: (k: string) => string, key: string, fallback: string): string {
  try {
    return t(key);
  } catch {
    return fallback;
  }
}

function SummaryRow({ parts }: { parts: string[] }) {
  if (parts.length === 0) return null;
  return (
    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-0.5 border-t pt-2 text-xs text-muted-foreground">
      {parts.map((p, i) => (
        <span key={i}>{p}</span>
      ))}
    </div>
  );
}

export function PregnancyExtendedSummary({ episode }: { episode: any }) {
  const t = useTranslations("Pregnancy");
  const parts: string[] = [];
  const tri = (v: unknown) => (v === true ? t("Bool_yes") : v === false ? t("Bool_no") : null);

  if (episode.risk_classification) {
    parts.push(
      `${t("RiskClassification")}: ${safeLabel(t, `Risk_${episode.risk_classification}`, episode.risk_classification)}`,
    );
  }
  const planned = tri(episode.planned_pregnancy);
  if (planned) parts.push(`${t("PlannedPregnancy")}: ${planned}`);
  if (episode.contraceptive_at_conception) {
    parts.push(`${t("ContraceptiveAtConception")}: ${episode.contraceptive_at_conception}`);
  }

  const gop = [episode.gravida, episode.para_vaginal, episode.para_cesarean, episode.abortions, episode.living_children];
  if (gop.some((x) => x != null)) {
    const n = (x: unknown) => (x == null ? "—" : String(x));
    parts.push(
      `${t("ObstetricHistory")}: G${n(episode.gravida)} · PV${n(episode.para_vaginal)} · PC${n(episode.para_cesarean)} · A${n(episode.abortions)} · NV${n(episode.living_children)}`,
    );
  }

  if (episode.imc_pre_gestational_class) {
    parts.push(
      `${t("ImcPreGestational")}: ${safeLabel(t, `Imc_${episode.imc_pre_gestational_class}`, episode.imc_pre_gestational_class)}`,
    );
  }

  const hi = listToChips(episode.preeclampsia_risk_factors);
  if (hi.length) parts.push(`${t("PreeclampsiaHigh")}: ${hi.map((k) => safeLabel(t, `PEF_${k}`, k)).join(", ")}`);
  const mo = listToChips(episode.preeclampsia_moderate_risk_factors);
  if (mo.length) parts.push(`${t("PreeclampsiaModerate")}: ${mo.map((k) => safeLabel(t, `PEM_${k}`, k)).join(", ")}`);

  const asa = tri(episode.aspirin_prophylaxis);
  if (asa) {
    const wk = episode.aspirin_start_week != null ? ` (${episode.aspirin_start_week}${t("Weeks")})` : "";
    parts.push(`${t("AspirinProphylaxis")}: ${asa}${wk}`);
  }

  const fh = episode.family_history as Record<string, unknown> | null;
  if (fh && typeof fh === "object") {
    const items = ["diabetes", "hipertensao", "gemelar"].filter((k) => fh[k] === true).map((k) => t(`FH_${k}`));
    if (typeof fh.outros === "string" && fh.outros) items.push(fh.outros);
    if (items.length) parts.push(`${t("FamilyHistory")}: ${items.join(", ")}`);
  }

  const mental = tri(episode.perinatal_mental_health_history);
  if (mental) parts.push(`${t("PerinatalMentalHealth")}: ${mental}`);
  const violence = tri(episode.domestic_violence_investigated);
  if (violence) parts.push(`${t("DomesticViolence")}: ${violence}`);

  if (episode.reference_maternity) parts.push(`${t("ReferenceMaternity")}: ${episode.reference_maternity}`);
  const linked = tri(episode.linked_to_maternity);
  if (linked) parts.push(`${t("LinkedToMaternity")}: ${linked}`);

  return <SummaryRow parts={parts} />;
}

export function VisitExtendedSummary({ visit }: { visit: any }) {
  const t = useTranslations("Pregnancy");
  const parts: string[] = [];
  const tri = (v: unknown) => (v === true ? t("Bool_yes") : v === false ? t("Bool_no") : null);

  if (visit.consultation_type) {
    parts.push(
      `${t("ConsultationType")}: ${safeLabel(t, `Consult_${visit.consultation_type}`, visit.consultation_type)}`,
    );
  }
  if (visit.main_care_provider) {
    parts.push(
      `${t("MainCareProvider")}: ${safeLabel(t, `Provider_${visit.main_care_provider}`, visit.main_care_provider)}`,
    );
  }
  const remote = tri(visit.remote_consult);
  if (remote) parts.push(`${t("RemoteConsult")}: ${remote}`);
  const dental = tri(visit.dental_health_activity);
  if (dental) parts.push(`${t("DentalHealthActivity")}: ${dental}`);
  const before12 = tri(visit.first_visit_before_12w);
  if (before12) parts.push(`${t("FirstVisitBefore12w")}: ${before12}`);

  const complaints = listToChips(visit.complaints);
  if (complaints.length) parts.push(`${t("Complaints")}: ${complaints.join(", ")}`);
  const warnings = listToChips(visit.warning_signs);
  if (warnings.length) parts.push(`${t("WarningSigns")}: ${warnings.join(", ")}`);
  const intercur = listToChips(visit.current_intercurrences);
  if (intercur.length) parts.push(`${t("CurrentIntercurrences")}: ${intercur.join(", ")}`);

  if (visit.edema_class) {
    parts.push(`${t("EdemaClass")}: ${safeLabel(t, `EdemaClass_${EDEMA_CLASS_KEY[visit.edema_class] ?? "ausente"}`, visit.edema_class)}`);
  }
  const leopold = tri(visit.leopold_done);
  if (leopold) parts.push(`${t("LeopoldDone")}: ${leopold}`);
  const onChart = tri(visit.fundal_height_recorded_on_chart);
  if (onChart) parts.push(`${t("FundalHeightOnChart")}: ${onChart}`);
  const bcf = tri(visit.bcf_change);
  if (bcf) parts.push(`${t("BcfChange")}: ${bcf}`);

  const pe = visit.physical_exam as Record<string, any> | null;
  if (pe && typeof pe === "object") {
    const altered = Object.keys(pe).filter((k) => pe[k]?.alteracao === true);
    const assessed = Object.keys(pe).filter((k) => pe[k]?.avaliado === true);
    if (assessed.length) {
      parts.push(`${t("PhysicalExam")}: ${assessed.map((k) => safeLabel(t, `PhysicalExam_${k}`, k)).join(", ")}`);
    }
    if (altered.length) {
      parts.push(
        `${t("ExamAlteration")}: ${altered.map((k) => safeLabel(t, `PhysicalExam_${k}`, k)).join(", ")}`,
      );
    }
  }

  const vs = visit.vaccination_status as Record<string, unknown> | null;
  if (vs && typeof vs === "object") {
    const set = Object.keys(vs).filter((k) => typeof vs[k] === "string" && vs[k]);
    if (set.length) {
      parts.push(
        `${t("VaccinationStatus")}: ${set
          .map((k) => `${safeLabel(t, `VaccinationStatus_${k}`, k)} ${safeLabel(t, `VS_${vs[k]}`, String(vs[k]))}`)
          .join(", ")}`,
      );
    }
  }
  const vg = visit.vaccines_in_gestation as Record<string, unknown> | null;
  if (vg && typeof vg === "object") {
    const rec = Object.keys(vg).filter((k) => vg[k] === true);
    if (rec.length) {
      parts.push(`${t("VaccinesInGestation")}: ${rec.map((k) => safeLabel(t, `Vac_${k}`, k)).join(", ")}`);
    }
  }

  const orientations = listToChips(visit.orientation_topics);
  if (orientations.length) parts.push(`${t("OrientationTopics")}: ${orientations.join(", ")}`);

  const weight = tri(visit.weight_gain_weekly_ok);
  if (weight) parts.push(`${t("WeightGainWeeklyOk")}: ${weight}`);
  const birthPlan = tri(visit.birth_plan_elaborated);
  if (birthPlan) parts.push(`${t("BirthPlanElaborated")}: ${birthPlan}`);

  return <SummaryRow parts={parts} />;
}
