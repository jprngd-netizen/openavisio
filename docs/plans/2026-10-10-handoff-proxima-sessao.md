# Handoff — próxima sessão (escrito 2026-10-10)

> Para retomar o projeto **OpenAvisio** (endurecimento clínico do prontuário) numa sessão nova.
> Leia isto + os planos referenciados antes de agir.

## 1. Onde estamos

| Frente | Estado |
|---|---|
| **R1** (safety clínico: WS-1..WS-5b, WS-4, WS-9) | ✅ **em produção** (deploy v0.8.0) |
| **R2** (WS-6 selo/versão · WS-7 imunizações+familiares · WS-8 vínculos exame/prescrição↔consulta · WS-10 continuidade) | ✅ **em produção** (deploy **v0.9.0**) |
| **WS-12** (suíte exercita o caminho de migração + drift genuíno) | ✅ mergeado |
| **MVP interação** (aviso via Memed) | ✅ commit `87dcb11` — **na branch, NÃO deployado** |
| **OB-1** (recurso `Pregnancy`) | 🔄 **rodando** (delegação `deleg_34214bea`, branch `feat/ob1-pregnancy`) |

- **Prod**: `health.gabrielsalem.com.br` (VPS `vpssp`, `/opt/stacks/openavisio`, :9340/9341). Versão **v0.9.0**,
  `alembic_version = a9b8c7d6e5f4`, backend/frontend `healthy`, smoke 307.
- **Branch base de trabalho**: `feat/prontuario-hardening`, head **`87dcb11`** (working tree limpo).
- **Alembic head**: **`a9b8c7d6e5f4`** (único). Cadeia:
  `o7b8c9d0e1f2 → w5a1b2c3d4e5 → x6b2c3d4e5f6 → y7c3d4e5f6a7 → z7v8w9x0y1z2 → a1c2o3m4p5g6 →
  c3e4f5a6b7d8 → c4f5a6b7d8e9 → d6f7a8b9c0d1 → e7f8a9b0c1d2 → a9b8c7d6e5f4`.
- **Suíte**: baseline **502 passed** (começou em 422). Dois caminhos verdes:
  `cd backend && uv run pytest -q` **e** `OA_TEST_SCHEMA=migrations uv run pytest -q`.
- **i18n**: pt/en/de com **1640** chaves idênticas. `tsc --noEmit` exit 0.

## 2. Primeira ação da próxima sessão

1. **Verificar o OB-1** quando a delegação voltar: `git log`, `alembic heads` (head único), `uv run pytest -q`
   (≥502), `OA_TEST_SCHEMA=migrations uv run pytest -q`, `pnpm exec tsc --noEmit`, paridade i18n.
2. Se verde → **merge ff** de `feat/ob1-pregnancy` na base e `push`.
3. Continuar a Parte A do escopo grande (ver §4).

## 3. Decisões vigentes (não reabrir sem nova decisão registrada)

- **DEC-1b**: obstetrícia = **episódio obstétrico completo** (pré-natal, consultas, exames, desfecho).
- **DEC-2b**: interação medicamentosa = base externa — **mas o MVP usa a Memed** (ver abaixo).
- **DEC-3**: taxonomia de `encounter_type` aprovada (aplicada no WS-10).
- **OB-DEC-1**: **GOP derivado** das gestações (sem campos gravida/para no `Patient`).
- **OB-DEC-2**: pré-natal = **tabela própria** (`PregnancyVisit`), NÃO reusar `Encounter`.
- **OB-DEC-3**: desfechos **completos** — parto vaginal/cesárea + abortamento (espontâneo/induzido) +
  ectópica + óbito fetal.
- **NOVO ESCOPO**: **seção de cuidados de enfermagem (geral + obstétrica)** — workstream OB-5 (a planejar).
- **Interação (MVP, owner 2026-10-10)**: checagem fica com a **Memed** (alerta nativo no módulo). Nosso
  engine (IX-1..IX-4: DDInter local + mapeamento ANVISA) vai para **backlog pós-MVP**. Limitação conhecida:
  medicação em texto livre fora da Memed **não** é checada automaticamente.
- **PRINCÍPIO DE PROJETO — "o registro é retrato da data"**: registro de consulta (e versão selada, WS-6)
  mostra o que era **fato naquela data**; nunca reescrito por valor derivado/atual. IG/GOP no registro são
  calculados **na data do atendimento**, não "hoje". Painéis vivos (meds ativas, GOP corrente) ficam fora
  do registro histórico. WS-3 (snapshot do CID no vínculo) e WS-6 (snapshot selado) já respeitam isso.

## 4. Próximos passos (escopo grande — Parte A)

`docs/plans/2026-10-10-escopo-grande-obstetricia-interacao.md` (Parte A + **Adendo**).

- **OB-1** 🔄 `Pregnancy` (modelo + migração + API + UI "Gestação"; DUM/DPP Naegele, correção por USG,
  IG `as_of`). *(em andamento)*
- **OB-2** pré-natal (`PregnancyVisit`, tabela própria) — campos obstétricos (IG, AU, BCF, apresentação,
  edema/PA), visível na timeline da gestação.
- **OB-3** desfecho/parto (completo, inclui abortamento/ectópica/óbito fetal) + dados do RN, encerra o episódio.
- **OB-4** integrações (Condition gestacional, vitais e exames via WS-8 ligados ao episódio).
- **OB-5** seção de **cuidados de enfermagem** (geral + obstétrica) — datada e congelada (retrato da data).
- **Backlog**: interação IX-1..IX-4 (`docs/plans/2026-10-10-parte-b-interacao.md`) — se o owner pedir a
  chave do **IMSES**, dá para adicionar a camada PT; senão, só **DDInter local** (`docs/research/2026-10-10-drug-interaction.md`).

## 5. Deploy / release (PHI — só com ok do Gabriel + backup)

- **deploy**: `./deploy/deploy.sh vpssp <tag> /opt/stacks/openavisio` — `git archive` do **tag**, rebuild,
  backend roda `alembic upgrade head` no startup.
- **backup antes**: `ssh vpssp 'U=$(docker exec openavisio-postgres printenv POSTGRES_USER);
  D=$(docker exec openavisio-postgres printenv POSTGRES_DB); docker exec openavisio-postgres pg_dump -U "$U" "$D"
  | gzip > /opt/stacks/openavisio/backups/vaultdb-pre-<tag>.sql.gz'` (backups em `/opt/stacks/openavisio/backups/`).
- **pendente**: subir o aviso de interação do MVP + a obstetrícia. Sugerido **empacotar** num próximo release
  (`v0.10.0`) após a obstetrícia, ou um `v0.9.1` só com o aviso.
- **rollback** = redeploy do tag anterior (migrações são aditivas/retrocompatíveis no que foi feito até aqui).

## 6. Como trabalhar (gotchas)

- **Subagentes compartilham working tree + banco de teste (`vaultdb_test`)** → workstreams **de schema rodam
  em série** com branches empilhadas sobre `feat/prontuario-hardening`. Verificar antes de mergear.
- Delegar: `hermes -p senna chat -q "<brief>" -Q` **ou** `delegate_task` (bg; o brief tem de ser
  autossuficiente — sessão nova não herda contexto). **Verificar o auto-relato antes de dar como feito.**
- Testes: `cd backend && uv run pytest -q` (132s). Postgres de teste no container `oa-pg`.
- **Frontend é Next.js 16** com breaking changes — ler `frontend/AGENTS.md` + `node_modules/next/dist/docs/`.
- `HTTP_422_UNPROCESSABLE_ENTITY` está deprecado no FastAPI — o repo ainda usa a constante (warning conhecido).

## 7. Pendências / bloqueios

- **Scratch DBs** `vaultdb_ws5bf`, `vaultdb_ws5chk` no `oa-pg` — não derrubados (gate de aprovação); inofensivos.
- Aviso de interação do MVP e obstetrícia **ainda não deployados** (prod = v0.9.0).
- `docs/plans/2026-10-09-prontuario-clinico-hardening.md` é o **plano-mestre** (R1/R2/WS-12); o de
  escopo grande cobre R3; `docs/research/2026-10-10-drug-interaction.md` tem a pesquisa de interação.

## 8. Mapa rápido de arquivos

- Planos: `docs/plans/2026-10-09-prontuario-clinico.md` (fundo), `...-hardening.md` (mestre),
  `2026-10-10-escopo-grande-obstetricia-interacao.md` (+Adendo), `2026-10-10-parte-b-interacao.md`, **este handoff**.
- Pesquisa: `docs/research/2026-10-10-drug-interaction.md`.
- Runbook: `docs/runbooks/migration-parity.md`.
- Backend: `backend/app/models/`, `backend/app/services/`, `backend/app/routers/`, `backend/alembic/versions/`,
  `backend/tests/` (conftest suporta `OA_TEST_SCHEMA=migrations`).
- Frontend: `frontend/src/app/patients/[id]/*`, `frontend/src/lib/{api,patientSections}.ts`,
  `frontend/src/messages/{pt,en,de}.json`.
- Deploy: `deploy/deploy.sh`.
