# Handoff — próxima sessão (atualizado 2026-10-11)

> Para retomar o **OpenAvisio** (endurecimento clínico) numa sessão nova. Leia isto + os planos referenciados.
> **Mudança de infra:** a VPS SP foi excluída em 2026-10-11; **produção agora roda LOCAL nesta VM (Ashburn)**.

## 1. Onde estamos

| Frente | Estado |
|---|---|
| **R1** (safety clínico: WS-1..WS-5b, WS-4, WS-9) | ✅ em produção |
| **R2** (WS-6 selo · WS-7 imunizações · WS-8 vínculos · WS-10 continuidade) | ✅ em produção (desde v0.9.0) |
| **WS-12** (suíte cobre o caminho de migração) | ✅ mergeado |
| **MVP interação** (aviso via Memed) | ✅ em produção (v0.10.0) |
| **OB-1** (`Pregnancy`) | ✅ mergeado + em produção |
| **OB-2** (pré-natal `PregnancyVisit`) | ✅ mergeado + em produção |
| **OB-3** desfecho/parto | ⬜ próximo |
| **OB-4** integrações · **OB-5** enfermagem (geral+obstétrica) | ⬜ a fazer |

- **Produção = LOCAL nesta VM (Ashburn, `vnic-oracle-vm-1-181196`)**, em `/opt/stacks/openavisio`, servida por
  `health.gabrielsalem.com.br → openavisio-frontend:3000` (Caddy local). Versão **v0.12.0**, head Alembic
  **`e2f3a4b5c6d7`**, 9 containers `healthy`, smoke 307.
- **Branch base**: `feat/prontuario-hardening` (head a atualizar; última = `9e05221`).
- **Suíte**: **519 passed** nos DOIS caminhos: `cd backend && uv run pytest -q` **e**
  `OA_TEST_SCHEMA=migrations uv run pytest -q`. `tsc --noEmit` exit 0; i18n pt/en/de **1672** chaves idênticas.
- **A VPS SP (`vpssp`) está MORTA** (SSH timeout). `deploy/deploy.sh <ssh-target>` **não serve mais** para prod.

## 2. Primeira ação da próxima sessão

Continuar o escopo grande (Parte A) com **OB-3 (desfecho/parto)**. Antes, puxar a base e confirmar o estado
(`git log`, `alembic heads`, `pytest`).

## 3. Decisões vigentes (não reabrir sem nova decisão registrada)

- **DEC-1b**: obstetrícia = **episódio obstétrico completo**. **OB-DEC-1**: GOP **derivado**. **OB-DEC-2**:
  pré-natal = **tabela própria** `PregnancyVisit` (feito no OB-2). **OB-DEC-3**: desfechos **completos** (parto
  vaginal/cesárea + abortamento espontâneo/induzido + ectópica + óbito fetal) — é o OB-3.
- **NOVO ESCOPO**: seção de **cuidados de enfermagem (geral + obstétrica)** — workstream OB-5.
- **Interação = MVP pela Memed** (alerta nativo). Engine próprio (IX-1..IX-4: DDInter local + ANVISA) = **backlog
  pós-MVP**; IMSES opcional se houver chave. Pesquisa: `docs/research/2026-10-10-drug-interaction.md`.
- **PRINCÍPIO "o registro é retrato da data"**: IG/GOP de um registro são calculados **na data do registro**,
  nunca "hoje"; painéis vivos ficam fora do histórico. (OB-1/OB-2 já seguem: IG `as_of`, não armazenada.)

## 4. Próximos passos (escopo grande — Parte A)

Plano: `docs/plans/2026-10-10-escopo-grande-obstetricia-interacao.md` (Parte A + **Adendo**).

- **OB-3** desfecho/parto (taxonomia completa OB-DEC-3) + dados do RN, encerra o episódio.
- **OB-4** integrações (Condition gestacional, vitais e exames via WS-8 ligados ao episódio).
- **OB-5** cuidados de enfermagem (geral + obstétrica) — datados e congelados (retrato da data).
- **Backlog**: interação IX-1..IX-4 (`docs/plans/2026-10-10-parte-b-interacao.md`).

## 5. Deploy / release — agora LOCAL (PHI: só com ok do Gabriel + backup)

1. **Backup primeiro**:
   `docker exec openavisio-postgres pg_dump -U openavisio vaultdb | gzip > /opt/stacks/openavisio/backups/vaultdb-pre-<tag>.sql.gz`
2. **Tag anotada** + push; depois extrair e rebuildar:
   ```bash
   git archive --format=tar <tag> | tar -x --no-same-owner -C /opt/stacks/openavisio
   (cd /opt/stacks/openavisio && docker compose up -d --build)
   ```
   O backend roda `alembic upgrade head` no startup. Sem `--delete` → `.env`/`data/`/`backups/` e arquivos
   não-rastreados ficam intactos.
3. **Verificar**: containers `healthy`; `docker exec openavisio-postgres psql -U openavisio -d vaultdb -tAc
   'select version_num from alembic_version;'` == novo head; `curl -o /dev/null -w '%{http_code}'
   https://health.gabrielsalem.com.br/` → **307**.
4. **⚠️ Rede de produção**: o Caddy local alcança o app pela rede externa **`vw-net`** (`health → openavisio-frontend:3000`).
   O anexo vive em `/opt/stacks/openavisio/compose.ashburn.yaml` (**não-rastreado**) + `COMPOSE_FILE=compose.yaml:compose.override.yaml:compose.ashburn.yaml`
   no `.env`. **Não** mover isso para arquivo rastreado — o `git archive` sobrescreve e o Caddy passa a dar **502**.
   Detalhe na skill `openavisio-dev`.
5. **Rollback** = redeploy do tag anterior (seguro se as migrações forem retrocompatíveis).

## 6. Como trabalhar (gotchas)

- **Subagentes compartilham working tree + banco de teste (`vaultdb_test`)** → workstreams de schema **em série**,
  branches empilhadas sobre `feat/prontuario-hardening`. **Corrida de branch:** commite mudanças de doc/plano na
  base **ANTES** de despachar um filho que faz `git checkout -b`, senão o merge deixa de ser ff.
- **Filho NÃO deve rodar o gate em background** (processo de subagente morre ao terminar → trabalho fica sem commit).
  Gate em **foreground**; commitar só com o gate verde. Se um filho travar, ler
  `.../cache/delegation/live/<id>/task-0.log` e re-despachar um filho "concluir esta branch" (não criar branch nova).
- **Verificar o auto-relato do filho** (`git log`, `alembic heads`, rodar pytest) — não aceitar como prova.
- Testes: `cd backend && uv run pytest -q` (~135s). Postgres de teste no container `oa-pg`.
- **Frontend é Next.js 16** com breaking changes — ler `frontend/AGENTS.md` + `node_modules/next/dist/docs/`.
- `HTTP_422_UNPROCESSABLE_ENTITY` está deprecado no FastAPI — o repo ainda usa a constante (warning conhecido).

## 7. Pendências / bloqueios

- **Interação** engine próprio (IX-1..IX-4) — backlog.
- Scratch DBs `vaultdb_ws5bf`, `vaultdb_ws5chk` no `oa-pg` — não derrubados (inofensivos).
- `docs/plans/2026-10-09-prontuario-clinico-hardening.md` é o **plano-mestre** (R1/R2/WS-12); o de escopo
  grande cobre R3; `docs/research/2026-10-10-drug-interaction.md` tem a pesquisa de interação.

## 8. Mapa rápido de arquivos

- Planos: `docs/plans/2026-10-09-prontuario-clinico.md` (fundo) · `...-hardening.md` (mestre) ·
  `2026-10-10-escopo-grande-obstetricia-interacao.md` (+Adendo) · `2026-10-10-parte-b-interacao.md` · **este**.
- Pesquisa: `docs/research/2026-10-10-drug-interaction.md`. Runbook: `docs/runbooks/migration-parity.md`.
- Skill do projeto: **`openavisio-dev`** (gate, migração, deploy local, gotcha vw-net).
- Backend: `backend/app/{models,services,routers,schemas}` · `backend/alembic/versions/` · `backend/tests/`
  (conftest suporta `OA_TEST_SCHEMA=migrations`).
- Frontend: `frontend/src/app/patients/[id]/*` (inclui `pregnancy/`) · `frontend/src/lib/{api,patientSections}.ts` ·
  `frontend/src/messages/{pt,en,de}.json`.

---

## Atualização — 2026-10-11 (Parte A entregue)

**Escopo grande (Parte A) COMPLETO e em produção (v0.12.0).** Workstreams obstétricos/enfermagem mergeados na
base `feat/prontuario-hardening` (`1111b97`): **OB-1** (`Pregnancy`), **OB-2** (`PregnancyVisit` pré-natal),
**OB-3** (`PregnancyOutcome`, taxonomia completa), **OB-4** (integrações: `PregnancyCondition` + vitais/exames
ligados ao episódio), **OB-5** (`NursingCare` — enfermagem geral/obstétrica). Suíte **541 passed** nos DOIS
caminhos, `tsc` 0, i18n pt/en/de, head Alembic **`e2f3a4b5c6d7`**. Tags: v0.10.0 → v0.11.0 → v0.12.0.

**Resta apenas:** backlog de interação (IX-1..IX-4, engine próprio; o MVP usou a Memed) —
`docs/plans/2026-10-10-parte-b-interacao.md`.