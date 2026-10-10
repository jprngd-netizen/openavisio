# Runbook — paridade migração ↔ modelos (WS-12 / RSK-5)

A suíte de testes historicamente construía o schema com
`Base.metadata.create_all` (`backend/tests/conftest.py`). Isso escondia qualquer
divergência entre as **migrações Alembic** (que a produção roda) e os **modelos
SQLAlchemy** (que a suíte roda): uma coluna criada `NOT NULL` por uma migração
mas não escrita pelo ORM só falha no caminho migrado. Foi exatamente o bug do
WS-5b (`calendar_events.start_at` legada `NOT NULL`, corrigido por
`z7v8w9x0y1z2`).

## Modo migração da suíte

A suíte passa a saber construir o schema pelas migrações reais:

```bash
cd backend
OA_TEST_SCHEMA=migrations TEST_DATABASE_URL=postgresql+asyncpg://openavisio:devpassword123@localhost:5432/vaultdb_test \
  uv run pytest -q
```

- `OA_TEST_SCHEMA` default = `create_all` (comportamento histórico, sem
  mudança no dia a dia).
- `OA_TEST_SCHEMA=migrations` faz o fixture de sessão **derrubar o schema
  (`DROP SCHEMA public CASCADE`) e reconstruí-lo com `alembic upgrade head`**
  — `create_all` **não** roda. O banco precisa existir (vazio); o schema é
  recriado do zero a cada sessão, então não é flaky.
- O `conftest.py` também **vincula o engine próprio do app**
  (`settings.database_url` → `AsyncSessionLocal` / `get_session_factory`) ao
  mesmo banco de teste. Sem isso, caminhos que não passam pelo `get_db`
  injetado (ex.: captura de prescrição) leem/escrevem o banco de **dev** e o
  run migrado passa "por acidente".

O `TEST_DATABASE_URL` deve conter `vaultdb_test` (guarda de segurança do
conftest).

## Drift aceito (cosmético)

`uv run alembic check` contra um DB migrado ainda reporta, **por design**:

1. **Colunas legadas de string ISO-8601** que a migração WS-5
   (`w5a1b2c3d4e5`) manteve ao lado das colunas tipadas, para rollback e
   limpeza posterior (estágio S5): `calendar_events.start_at/end_at`,
   `conditions.recorded_date/onset_date_time/abatement_date_time`,
   `encounters.encounter_date`,
   `medication_statements.effective_start/effective_end/date_asserted`,
   `observations.effective_date_time`, `patients.birth_date`. São **nullable**
   e o ORM não as mapeia — inertes.
2. **Nomes de constraint vs índice único** (`uq_*` / `ix_*`): a unicidade é
   garantida nos dois casos; só o nome difere. Ex.: `data_categories.code`,
   `document_share_links.token_hash`, `passkey_credentials.credential_id`,
   `patient_caregiver_invites.token`, `patient_keys.patient_id`,
   `task_runs.task_id`.

Ambos são cosméticos (sem efeito funcional) e **não** são perseguidos.

## Drift corrigido

A migração `a9b8c7d6e5f4_reconcile_model_not_null_drift` alinha ao modelo as
colunas que as migrações deixaram `nullable` embora o ORM as declare
`NOT NULL`: `start_at_ts` em `calendar_events`; `created_at`/`updated_at`/
`is_deleted` em `clinical_histories`, `document_favorites`, `patient_favorites`,
`patient_keys`; e `organization.default_language`. Cada coluna tem
`server_default`, então o `SET NOT NULL` é seguro (com backfill defensivo).
