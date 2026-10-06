"use client";

import { useState } from "react";
import { updatePrescriberAction } from "./actions";
import { getMemedReferenceData } from "@/lib/api";

const UF_LIST = [
  "AC","AL","AP","AM","BA","CE","DF","ES","GO","MA","MT","MS",
  "MG","PA","PB","PR","PE","PI","RJ","RN","RO","RS","RR","SC",
  "SE","SP","TO",
];

const SEX_OPTIONS = [
  { value: "M", label: "Male" },
  { value: "F", label: "Female" },
  { value: "O", label: "Other" },
];

interface ReferenceItem {
  id: number;
  name: string;
}

export function PrescriberForm({
  initial,
  isNew,
  users = [],
  cities = [],
  specialties = [],
}: {
  initial: any | null;
  isNew: boolean;
  users?: any[];
  cities?: { id: number; name: string }[];
  specialties?: { id: number; name: string }[];
}) {
  const [givenName, setGivenName] = useState(initial?.given_name ?? "");
  const [familyName, setFamilyName] = useState(initial?.family_name ?? "");
  const [cpf, setCpf] = useState("");
  const [birthDate, setBirthDate] = useState(initial?.birth_date ?? "");
  const [boardCode, setBoardCode] = useState(initial?.board_code ?? "");
  const [boardNumber, setBoardNumber] = useState(initial?.board_number ?? "");
  const [boardState, setBoardState] = useState(initial?.board_state ?? "");
  const [email, setEmail] = useState(initial?.email ?? "");
  const [phone, setPhone] = useState(initial?.phone ?? "");
  const [sex, setSex] = useState(initial?.sex ?? "");
  const [cityId, setCityId] = useState<number | null>(initial?.city_id ?? null);
  const [specialtyId, setSpecialtyId] = useState<number | null>(initial?.specialty_id ?? null);
  const [userId, setUserId] = useState(initial?.user_id ?? "");

  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [savedData, setSavedData] = useState<any>(null);

  // Reference data (passed from server component, mutable for search)
  const [mutableCities, setCities] = useState(cities);
  const [mutableSpecialties, setSpecialties] = useState(specialties);
  const [citySearch, setCitySearch] = useState("");
  const [specialtySearch, setSpecialtySearch] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError("");
    setSaved(false);
    setSavedData(null);

    const fields: {
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
    } = {
      given_name: givenName.trim(),
      family_name: familyName.trim(),
    };

    // On create, CPF is required; on update, blank preserves existing
    if (isNew || cpf.trim()) {
      fields.cpf = cpf.trim();
    }
    if (birthDate.trim()) fields.birth_date = birthDate.trim();
    if (boardCode.trim()) fields.board_code = boardCode.trim();
    if (boardNumber.trim()) fields.board_number = boardNumber.trim();
    if (boardState.trim()) fields.board_state = boardState.trim();
    if (email.trim()) fields.email = email.trim();
    if (phone.trim()) fields.phone = phone.trim();
    if (sex) fields.sex = sex;
    if (cityId) fields.city_id = cityId;
    if (specialtyId) fields.specialty_id = specialtyId;
    if (userId) fields.user_id = userId;

    const result = await updatePrescriberAction(fields);
    setSaving(false);

    if (result.error) {
      setError(result.error);
    } else {
      setSaved(true);
      setSavedData(result.data);
      // Clear CPF field after save — never show full CPF
      setCpf("");
    }
  }

  async function searchCities(q: string) {
    setCitySearch(q);
    if (q.length < 1) return;
    const results = await getMemedReferenceData("cities", q).catch(() => [] as ReferenceItem[]);
    setCities(results);
  }

  async function searchSpecialties(q: string) {
    setSpecialtySearch(q);
    if (q.length < 1) return;
    const results = await getMemedReferenceData("specialties", q).catch(() => [] as ReferenceItem[]);
    setSpecialties(results);
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-6">
      {/* Saved indicator */}
      {saved && savedData && (
        <div className="rounded-lg border border-green-500 bg-green-50/30 dark:bg-green-950/20 px-4 py-3 text-sm">
          <p className="font-medium text-green-700 dark:text-green-300">Prescriber saved.</p>
          {savedData.cpf_last4 && (
            <p className="text-xs text-muted-foreground mt-1">
              CPF: ***{savedData.cpf_last4}
            </p>
          )}
          {savedData.memed_status && (
            <p className="text-xs text-muted-foreground mt-1">
              Memed status: {savedData.memed_status}
            </p>
          )}
        </div>
      )}

      {/* Name fields */}
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <label className="text-sm font-medium">
            Given name <span className="text-destructive">*</span>
          </label>
          <input
            type="text"
            value={givenName}
            onChange={(e) => setGivenName(e.target.value)}
            required
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
          />
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">
            Family name <span className="text-destructive">*</span>
          </label>
          <input
            type="text"
            value={familyName}
            onChange={(e) => setFamilyName(e.target.value)}
            required
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
          />
        </div>
      </div>

      {/* CPF + Birth date */}
      <div className="grid gap-3 sm:grid-cols-2">
        <div className="space-y-1">
          <label className="text-sm font-medium">
            CPF {isNew && <span className="text-destructive">*</span>}
            {!isNew && <span className="text-xs text-muted-foreground"> (leave blank to keep existing)</span>}
          </label>
          <input
            type="text"
            value={cpf}
            onChange={(e) => setCpf(e.target.value)}
            placeholder={isNew ? "" : "Leave blank to preserve"}
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
          />
          {!isNew && initial?.cpf_last4 && (
            <p className="text-xs text-muted-foreground">Current: ***{initial.cpf_last4}</p>
          )}
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">
            Birth date {isNew && <span className="text-destructive">*</span>}
          </label>
          <input
            type="date"
            value={birthDate}
            onChange={(e) => setBirthDate(e.target.value)}
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
          />
        </div>
      </div>

      {/* Board fields */}
      <fieldset className="rounded-lg border bg-card p-4 space-y-3">
        <legend className="text-sm font-semibold px-1">Professional board</legend>
        <div className="grid gap-3 sm:grid-cols-3">
          <div className="space-y-1">
            <label className="text-sm font-medium">
              Code <span className="text-destructive">*</span>
            </label>
            <input
              type="text"
              value={boardCode}
              onChange={(e) => setBoardCode(e.target.value)}
              placeholder="CRM"
              required={isNew}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">
              Number <span className="text-destructive">*</span>
            </label>
            <input
              type="text"
              value={boardNumber}
              onChange={(e) => setBoardNumber(e.target.value)}
              placeholder="12345"
              required={isNew}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">
              State <span className="text-destructive">*</span>
            </label>
            <select
              value={boardState}
              onChange={(e) => setBoardState(e.target.value)}
              required={isNew}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
            >
              <option value="">—</option>
              {UF_LIST.map((uf) => (
                <option key={uf} value={uf}>{uf}</option>
              ))}
            </select>
          </div>
        </div>
      </fieldset>

      {/* Memed reference data */}
      <fieldset className="rounded-lg border bg-card p-4 space-y-3">
        <legend className="text-sm font-semibold px-1">Memed reference data</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <label className="text-sm font-medium">City</label>
            <input
              type="text"
              value={citySearch}
              onChange={(e) => searchCities(e.target.value)}
              placeholder="Search city…"
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
            />
{mutableCities.length > 0 && (
                <select
                  value={cityId ?? ""}
                  onChange={(e) => setCityId(e.target.value ? parseInt(e.target.value) : null)}
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm mt-1"
                  size={Math.min(mutableCities.length, 5)}
                >
                  <option value="">—</option>
                  {mutableCities.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            )}
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">Specialty</label>
            <input
              type="text"
              value={specialtySearch}
              onChange={(e) => searchSpecialties(e.target.value)}
              placeholder="Search specialty…"
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
            />
{mutableSpecialties.length > 0 && (
                <select
                  value={specialtyId ?? ""}
                  onChange={(e) => setSpecialtyId(e.target.value ? parseInt(e.target.value) : null)}
                  className="w-full rounded-lg border bg-background px-3 py-2 text-sm mt-1"
                  size={Math.min(mutableSpecialties.length, 5)}
                >
                  <option value="">—</option>
                  {mutableSpecialties.map((s) => (
                  <option key={s.id} value={s.id}>{s.name}</option>
                ))}
              </select>
            )}
          </div>
        </div>
      </fieldset>

      {/* Contact fields */}
      <fieldset className="rounded-lg border bg-card p-4 space-y-3">
        <legend className="text-sm font-semibold px-1">Contact</legend>
        <div className="grid gap-3 sm:grid-cols-2">
          <div className="space-y-1">
            <label className="text-sm font-medium">Email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
            />
          </div>
          <div className="space-y-1">
            <label className="text-sm font-medium">Phone</label>
            <input
              type="text"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
            />
          </div>
        </div>
        <div className="space-y-1">
          <label className="text-sm font-medium">Sex</label>
          <select
            value={sex}
            onChange={(e) => setSex(e.target.value)}
            className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
          >
            <option value="">—</option>
            {SEX_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>{o.label}</option>
            ))}
          </select>
        </div>
      </fieldset>

      {/* User selection */}
      <div className="space-y-1">
        <label className="text-sm font-medium">Linked user (authorized issuer)</label>
        <p className="text-xs text-muted-foreground">Only this user can issue prescriptions through Memed.</p>
        <select
          value={userId}
          onChange={(e) => setUserId(e.target.value)}
          className="w-full rounded-lg border bg-background px-3 py-2 text-sm"
        >
          <option value="">—</option>
          {users.map((u: any) => {
            const name = [u.first_name, u.last_name].filter(Boolean).join(" ");
            return (
              <option key={u.id} value={u.id}>
                {name || u.email} ({u.email})
              </option>
            );
          })}
        </select>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}

      <button
        type="submit"
        disabled={saving}
        className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium disabled:opacity-50"
      >
        {saving ? "Saving…" : (isNew ? "Create prescriber" : "Save prescriber")}
      </button>
    </form>
  );
}