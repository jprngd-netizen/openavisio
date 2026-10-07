# Prontuário — Consultas/Evolução (SOAP) + Localização do Admin

**Data:** 2026-10-07 · **Branch:** `feat/prontuario-receitas` · **Autor:** Senna (orquestrador)
**Workspace:** `~/openavisio` (VPS Oracle, clone do fork `jprngd-netizen/openavisio`).

## Objetivo

1. **Prontuário**: adicionar o registro clínico de **consulta/evolução** (SOAP: Subjetivo/anamnese,
   Objetivo/exame físico, Avaliação/diagnóstico, Plano/conduta) + CID-10, vinculado ao paciente.
2. **Localização**: traduzir/localizar a página `/admin/organization` (rótulos hoje em inglês e a
   seção legal alemã §5 DDG) para pt/en/de, com enquadramento **LGPD** em pt-BR; expor `pt` no
   seletor de idioma (hoje só en/de).

## Reuso (não reinventar)

- **Formas FHIR R4** (`Encounter` + nota clínica): nomes de campos alinhados ao padrão. Sem
  dependência nova — o app já é FHIR-flavored (Observation/Condition) e não usa `@medplum/*`
  nem `fhir.resources`.
- **Padrão de UI SOAP** já provado (Medplum chart demo / Pyronis). Implementar com os componentes
  que o app já tem (Radix + Tailwind + next-intl + server actions).
- Sem plataforma externa (Medplum/openEHR substituiriam a camada de dados/auth — rejeitado).

## Contrato da API (backend)

- `GET  /api/patients/{patient_id}/encounters` → `list[EncounterDto]` (ordenado por `encounter_date` desc)
- `POST /api/patients/{patient_id}/encounters` → `EncounterDto` (201)
- `GET  /api/encounters/{id}` → `EncounterDto`
- `PATCH /api/encounters/{id}` → `EncounterDto`
- `DELETE /api/encounters/{id}` → 204 (soft delete `is_deleted=True`)

`EncounterDto`: `id`, `patient_id`, `status` ("finished"), `encounter_type`, `encounter_date`
(ISO 8601), `chief_complaint`, `history`, `physical_exam`, `assessment`, `plan`, `cid10_code`,
`cid10_display`, `notes`, `created_at`, `updated_at`.

Acesso: `require_patient_access`; create/update/delete exigem `AccessLevel.contribute` (espelhar
`routers/observations.py`).

## Migração

`down_revision = "i1a2b3c4d5e6"` (head atual). Nova tabela `encounters`.

## Frontend

- `lib/patientSections.ts`: nova seção `Encounters` (segment `encounters`, ícone `Stethoscope`).
- Rota `app/patients/[id]/encounters/page.tsx` (server component) + painel/editor cliente.
- `lib/api.ts`: server actions `getEncounters`, `createEncounter`, `updateEncounter`, `deleteEncounter`.
- i18n: `Patient.Encounters` (+desc) e namespace `Enc`.

## Verificação

- Backend: `uv run python -c "import app.main"`; `uv run alembic heads` (1 head novo);
  `uv run alembic upgrade head` contra Postgres local (docker) + `POST/GET` de encounter.
- Frontend: `pnpm run build` (type-check) + `pnpm run lint`.
- Deploy: tag → archive → `docker compose up -d --build` na VPS SP.