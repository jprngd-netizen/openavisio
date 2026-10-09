# Prontuário clínico — remoção do ocupacional + remoção do bloqueio de compartilhamento

**Data:** 2026-10-09 · **Branch:** `feat/prontuario-receitas` · **Autor:** Senna
**Workspace:** `~/openavisio` (VPS Oracle, clone do fork `jprngd-netizen/openavisio`).

## 1. Prontuário: clínico, não ocupacional

Decisão do Gabriel: o prontuário é **clínico** (uso pessoal/família). A estrutura de saúde
ocupacional (padrão Petrobras/SESMT) foi **descartada**. Mantido o que faz sentido clínico,
remanejado; o resto removido.

| Antes (ocupacional) | Depois (clínico) |
|---|---|
| Taxonomia 9 grupos / 39 itens (`occupationalSections.ts`) | removida |
| Índice `/patients/[id]/prontuario` + páginas por seção | removidos |
| Capa (identidade + **vínculo empregatício** + cabeçalho) | **Capa** (`/patients/[id]/cover`): identidade + cabeçalho, sem vínculo |
| Seção #2 "História Clínica e Ocupacional" (+ empregos/exposições) | **Antecedentes** (`/patients/[id]/antecedents`): antecedentes pessoais/familiares/cirúrgicos, alergias, hábitos |
| Colunas de vínculo no `Patient` (8) | removidas |
| `previous_employments` / `exposures` (JSONB) | removidos |

As duas seções entram em `frontend/src/lib/patientSections.ts` (fonte única do sidebar desktop,
aba "Mais" mobile, switcher e tiles). i18n: namespaces `Cover` e `Antecedents`; `Occupational`
removido (paridade pt/en/de mantida). Migração `o7b8c9d0e1f2` dropa as 10 colunas.

**O que falta (não implementado):**
- Alergias ainda são texto livre (não há recurso estruturado tipo `AllergyIntolerance`).
- Antecedentes familiares textuais (sem estrutura por parentesco).
- Sem recurso de vacinas/imunizações próprio.
- Capa é só leitura + link para editar o cadastro (sem “médico responsável”, por escolha).
- Export/impressão não foi revalidado ponta a ponta após a mudança.

## 2. Compartilhamento externo: removido o bloqueio de staff

`require_share_management` (`backend/app/services/share_link.py`) não bloqueia mais staff: sem
acesso → **404**; qualquer usuário com acesso (caregiver **ou** staff) pode criar/gerir share
links. Removidos a constante `_STAFF_ROLES` e o 403 "External sharing is reserved for a
patient's caregivers or legal representatives, not staff." `created_legal` continua registrado.
ADRs 021/025/027 anotados. Funcionalidade (`ShareWithSpecialistPanel`) intacta.

## Verificação

- Backend: `uv run python -c "import app.main"` OK; `uv run alembic heads` = `o7b8c9d0e1f2` (1 head).
- `uv run pytest -q` → **422 passed** (suíte completa).
- Frontend: `pnpm exec tsc --noEmit` OK; `pnpm run build` OK (rotas `/cover` e `/antecedents`
  compiladas; `/prontuario` ausente); i18n parity OK (pt/en/de).

## Não verificado / limites

- Sem e2e contra a app rodando (Playwright) e sem deploy — não exercitado no boundary real.
- Migração não aplicada no banco de produção (dev apenas).
- Lint do repo tem ~365 erros pré-existentes (`no-explicit-any`); não é gate (o build passa).
