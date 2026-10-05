# Prontuário Digital + Receituário Eletrônico (SNCR/ANVISA) — Plano de Ataque

**Data:** 2026-10-05 · **Branch:** `feat/prontuario-receitas` · **Autor:** Senna (orquestrador)

## 1. Objetivo

Transformar `health.gabrielsalem.com.br` (OpenAvisio) em um **prontuário médico digital pessoal** com:

1. Geração de prescrição médica (receituário).
2. Obtenção dos **números oficiais de receituário via API do SNCR/ANVISA**.
3. **Salvamento automático** do documento.
4. **Assinatura digital ICP-Brasil (BirdID)** — via agregador.

**Escopo:** uso pessoal (1 prescritor). Não é produto/SaaS.

## 2. Estado atual (verificado 2026-10-05)

- Roda na **VPS SP** (`vpssp`, `100.112.1.69`), `/opt/stacks/openavisio`, 8 containers `healthy` (uptime ~4d). Frontend `:9340`, backend `:9341`.
- Público: `health.gabrielsalem.com.br` → edge Caddy → `100.112.1.69:9340`. O Caddyfile **vivo** é `/opt/stacks/caddy/conf/Caddyfile` (o `/opt/stacks/caddy/Caddyfile` está obsoleto).
- Código = upstream `codeberg.org/openavisio/openavisio` v0.1.0-beta3 (projeto alemão, posicionado como "não dispositivo médico"). Stack: FastAPI (Python 3.12) + Next.js 16 + Postgres/pgvector + Redis + Celery + aiservice (LLM via OmniRoute).
- Já existe: pacientes, documentos (OCR + extração por IA), observações, condições, medicamentos, agenda, criptografia envelope AES-256-GCM por paciente, share links, passkeys, i18n (locale `pt`).
- **Não existe**: prescrição, assinatura, ANVISA.
- O deploy na VPS está **sem `.git`** (risco operacional). Dev no Mac Mini em `/opt/stacks/openavisio` (clone upstream + patches locais); branch `feat/prontuario-receitas` criada com baseline commitado.

## 3. Decisões travadas

- **Assinatura:** via agregador (Prescreve/Prescri), que já embrulha BirdID/A1/ICP-Brasil + token de validação.
- **Escopo:** uso pessoal (1 prescritor).
- **Dev → deploy:** desenvolve no Mac Mini (opencode), deploy na VPS SP.

## 4. Fatos técnicos — SNCR (fonte: Manual da API v5, ANVISA; cópias em `docs/sncr/`)

- **Base URL:** homolog `https://api-gateway.hmg.apps.anvisa.gov.br/api-sncr/api/v1/` · prod `https://api-gateway.prd.apps.anvisa.gov.br/api-sncr/api/v1/`.
- **Auth:** OAuth2/OIDC via **Gov.br** (Keycloak). `GET /auth/login?client_url=<url>` → redirect → retorno com `?session_id=` → `GET /auth/token?session_id=` → JWT `access_token`. Frontend precisa estar em domínio **`.br`** (CORS cross-domain suportado). Não há API key fixa: a sessão é do próprio prescritor.
- **Endpoints de numeração:**
  - `POST /numeracoes/notificacao-receita` — `receita` (NRA|NRB|NRB2|NRR|NRT), `conselho` (CRM|CRMV|CRO), `uf`, `documento`, `quantidade` (10–50).
  - `POST /numeracoes/receita-especial-retencao` — `conselho`, `tipo` (RCE|RET), `documento`, `uf`, **`cnpj`** (empresa responsável pela plataforma). Até 1000 por requisição.
- **Regras:** o prescritor precisa estar cadastrado no SNCR (cadastro automático no 1º auth; exige inscrição ativa em conselho). Em produção, a numeração de Notificação de Receita depende de aprovação prévia da Vigilância Sanitária (em teste/homolog, sem aprovação prévia).
- **Não há credenciamento de plataforma**, mas **RCE/RET exige CNPJ válido** da empresa consumidora da API.
- O SNCR **só numera**. A **assinatura eletrônica** (ICP-Brasil qualificada, ou avançada) é responsabilidade da plataforma.
- Material de apoio oficial: Manual da API v5, Instruções de Integração v1.0, **aplicação-exemplo** (`docs/sncr/exemplo-integracao-v2.zip`), P&R RDC 1.000/2025.
- **Status:** API disponibilizada para integração em 01/10/2026. RDC 1.028/2026 prorrogou a operação plena para 30/09/2026 (data já passada — reconfirmar estado atual no portal).

## 5. Assinatura (BirdID / ICP-Brasil)

- BirdID = certificado A3 em nuvem da **Soluti**. CFM Res. 2.299/2021 exige ICP-Brasil com NGS2.
- **Caminho escolhido:** API de **agregador** — emite + assina + gera token de validação + notifica o paciente, com sandbox. Referências: Prescreve (`prescreve.com/api`) e Prescri (`prescri.com.br/api-bird-id`).
- Alternativa (fora de escopo agora): BirdID direto na Soluti.

## 6. Arquitetura proposta

Módulo novo **"Prescrições"** no backend (`routers/prescriptions.py` + `models/prescription.py` + schemas) + tela no frontend, plugado em `Patient`/`Document`:

1. Cadastro do prescritor (CRM/UF/CPF) + credencial do agregador.
2. Fluxo de auth Gov.br (SNCR) — reaproveitar a aplicação-exemplo da ANVISA.
3. Puxar numeração no SNCR conforme o tipo de receita.
4. Montar o PDF no modelo RDC 1.000/2025 (com o número alocado + QR).
5. Assinar via agregador (BirdID) → PDF assinado + token/link de validação.
6. **Salvar automaticamente** usando o `Document` existente (envelope encryption, retenção 20 anos) + link de validação.
7. **Autosave** do rascunho durante a edição.

Princípio: mudar o upstream o mínimo possível — feature isolada, seguindo nomes/idioma e ADRs do projeto.

## 7. Fases (passo a passo)

- **F0 — Fundação:** repo/branch no Mac, baseline, docs SNCR no repo (`docs/sncr/`), `AGENTS.md` do projeto, build/test local. *(branch + docs: feito)*
- **F1 — Domínio:** modelar Prescrição (tipos NRA/NRB/NRB2/NRR/NRT/RCE/RET), vínculo com `Patient`, estados (rascunho → numerada → assinada → dispensada), autosave.
- **F2 — SNCR auth:** fluxo OAuth Gov.br (backend + frontend), tokens, ambiente de homologação.
- **F3 — SNCR numeração:** clients para os 2 endpoints, tratamento de erros/limites, persistência dos números.
- **F4 — Geração de PDF:** templates por tipo (RDC 1.000/2025) + QR.
- **F5 — Assinatura:** integração com o agregador (sandbox), webhook, PDF assinado, token de validação.
- **F6 — Autosave + arquivamento:** salvar no `Document`, criptografia, retenção, link público de validação.
- **F7 — Validação ponta a ponta** em homolog + deploy na VPS SP + testes e2e.

Cada fase tem critério de aceite explícito e um teste que falha sem a correção.

## 8. Riscos e gates

- **CNPJ obrigatório** para numeração RCE/RET (empresa responsável pela plataforma) → decidir CNPJ ou restringir o escopo inicial às receitas que não o exigem.
- Numeração de Notificação de Receita depende de aprovação da Vigilância Sanitária em produção.
- Assinatura: contratar agregador (custo) + certificado BirdID.
- **Regulatório:** isso transforma um "não dispositivo médico" em **PEP regulado** (CFM 1.821/2007, SBIS, LGPD art. 11 — dados sensíveis —, RDC 1.000/2025). Mudança de posição precisa ser consciente.
- Deploy atual sem git: resolver versionamento.

## 9. Fora de escopo (por ora)

- Multi-médico / SaaS.
- Integração direta com a Soluti.
- Assinatura de NRA/talidomida/retinoides (talonário físico por ora).

## 10. Como rodar (opencode + planner)

- Diretório: `/opt/stacks/openavisio` (Mac Mini).
- Agentes do `oh-my-openagent`: **Prometheus (Plan Builder)**, Metis (Plan Consultant), Momus (Plan Critic).
- Modelo funcional hoje: `opencode/nemotron-3-ultra-free` (free). Os `omnirouter/cc/*` estão com **auth expirada** no OmniRoute.
- Exemplo:
  `opencode run --agent "Prometheus - Plan Builder" --model opencode/nemotron-3-ultra-free "<prompt>"`

## 11. Decisão (2026-10-05): integração via Memed

Escolhido: **Memed (Sinapse Prescrição)** como plataforma de prescrição + assinatura; **certificado BirdID próprio** (BYOC, plano anual com créditos); **CNPJ do SNCR = da Memed** (não abrimos CNPJ).

Consequências (substitui o desenho "direto ao SNCR" das seções 5–6):

- **Numeração SNCR:** obtida pela Memed (auth Gov.br do prescritor dentro do fluxo Memed). **Não** integramos a API do SNCR.
- **Assinatura ICP-Brasil:** executada pela Memed usando o **certificado próprio** do prescritor (nosso BirdID). A Memed não cobra a assinatura; ela consome os créditos do nosso BirdID.
- **Integração:** módulo frontend da Memed embutido (`sinapse-prescricao`) + API REST de backend (`api-key` + `secret-key`, ambientes homologação e produção).
- **O que ainda construímos:** modelar `Prescription` no OpenAvisio, guardar o PDF assinado como `Document` (envelope encryption, **sem** disparar OCR), link de validação, autosave do rascunho, auditoria.
- **O que sai do escopo:** integração direta ao SNCR, motor de assinatura próprio, geração de PDF própria, abertura de CNPJ.

Fases afetadas: **F2/F3/F4/F5 → "integração Memed"** (credenciais, embed do módulo, callback do PDF assinado). **F1 (domínio) permanece**, simplificada.

A confirmar no onboarding: preço da API de parceiro (o ToS indica licença gratuita; não há tabela pública) e o formato exato do retorno do PDF assinado.

### Integração Memed — fatos confirmados (doc oficial, 2026-10-05)

- **API** — homolog: `https://integrations.api.memed.com.br/v1` · prod: `https://api.memed.com.br/`
- **Script (frontend)** — homolog: `https://integrations.memed.com.br/modulos/plataforma.sinapse-prescricao/build/sinapse-prescricao.min.js`
- **Chaves** — o par de homologação é **fixo e público** (está na própria doc); validadas com `GET /v1/sinapse-prescricao/check-key` → `{"code":"chave-valida"}` (HTTP 200).
- **Disponibilidade homolog** — indisponível das 0h às 6h (seg–sex) e todo o fim de semana.
- **Fluxo** — o backend cadastra o prescritor e recebe um `data-token`; o frontend carrega o script com `data-token` e aciona `MdHub`/`MdSinapsePrescricao` (`setPaciente`, `show`, etc.).
- **Cadastro do prescritor exige** — id externo, nome, sobrenome, CPF, registro profissional + UF, especialidade, cidade.
- **Armazenado em** — `.env` (gitignored) no repo: `MEMED_API_URL`, `MEMED_SCRIPT_URL`, `MEMED_API_KEY`, `MEMED_SECRET_KEY`.

### Validação ponta a ponta em homologação (2026-10-05)

- **Backend:** `check-key` OK; `GET /cidades` e `GET /especialidades` OK; `POST /sinapse-prescricao/usuarios` → **201** cria o prescritor (status "Em análise", pois o CRM fictício não passa na validação do CFM) e retorna o `token`; `GET /sinapse-prescricao/usuarios/{cpf|external_id}` recupera os dados + token (o token **muda a cada chamada**).
- **Frontend:** uma página de teste carregou `sinapse-prescricao.min.js` com `data-token`; o módulo criou o iframe `https://v4-embedded-integrations.memed.com.br/?embedded=1&mode=fullscreen&token=...&partner=3` e **renderizou a UI de prescrição** (abas Arquivo/Modelos/Ajuda, "Adicionar à prescrição", botão "Gerar Prescrição", toggle **Assinatura Digital**).
- **Detalhe de integração:** os eventos (`core:moduleInit`, `core:moduleShow`, `core:allmodulesareready`, `core:prescricaoImpressa`, …) chegam por **postMessage** na `window`, **não** como eventos DOM no documento pai. Abrir o módulo: `MdHub.command.send('plataforma.prescricao','show')`.
- **Artefato de teste:** `memed-test/` (fora do repo OpenAvisio). Navegador via `agent-browser` + Chromium do sistema (`AGENT_BROWSER_EXECUTABLE_PATH=/usr/local/bin/chromium`).

## Fontes

- ANVISA — SNCR: https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/sncr
- ANVISA — Documentos do SNCR (manual API, instruções, app-exemplo, P&R RDC 1.000): https://www.gov.br/anvisa/pt-br/assuntos/medicamentos/controlados/sncr/documentos-do-sncr
- Prescreve — API: https://www.prescreve.com/api · Prescri — API BirdID: https://www.prescri.com.br/api-bird-id
- CFM — Resolução 2.299/2021 (assinatura ICP-Brasil em documentos médicos)
