# OpenAvisio

**Prontuário eletrônico self-hosted para cuidado compartilhado — com IA local, criptografia por paciente e conformidade LGPD.**

> Fork brasileiro de um prontuário open-source alemão (AGPL-3.0), reconstruído por um médico
> do trabalho para o contexto clínico brasileiro: prontuário SOAP, obstetrícia, enfermagem
> obstétrica, prescrição eletrônica (Memed/SNCR) e conformidade LGPD/ANPD.

O OpenAvisio é um **servidor de prontuário** que roda na sua máquina. Você sobe documentos
médicos (PDFs, laudos, exames, imagens) e a IA local lê, classifica e extrai os dados
estruturados — diagnósticos, medicações, medidas, resultados de laboratório — direto para o
prontuário do paciente. A partir daí o sistema mantém o **registro clínico** de verdade:
consultas com nota SOAP, CID-10, sinais vitais, alergias, imunizações, obstetrícia completa,
prescrições assinadas com ICP-Brasil.

Nada sai da sua infraestrutura. Nem os dados, nem a IA.

---

## Por que existe

Projeto nascido de uma necessidade concreta: prontuário de verdade, no consultório, sem
depender de SaaS que trata dado clínico como commodity. Os três eixos:

- **O dado é seu, e o servidor é seu.** AGPL-3.0, self-hosted, envelope encryption por
  paciente. Apagar um paciente destrói a chave dele — *crypto-shredding* que alcança os
  backups. Não existe multi-tenancy: uma instalação serve uma organização.
- **IA local, ou nenhuma.** OCR, classificação, extração, chat e embeddings rodam no seu
  Ollama/vLLM. Sem egress para nuvem a menos que você ligue isso de propósito.
- **Conformidade embutida.** DPIA, RoPA, checklist LGPD/ANPD, runbook de resposta a
  incidentes e template de contrato em `docs/`. A documentação que um consultório
  realmente precisa para operar legalmente.

---

## O que faz

### Prontuário clínico (o núcleo)

Uma consulta (`Encounter`) é uma entrada completa de prontuário:

- **Nota SOAP** — queixa principal, história, exame físico, avaliação, plano.
- **N diagnósticos** — múltiplos CID-10 por consulta, cada um gerando/atualizando uma
  `Condition` na lista de problemas com proveniência (origem rastreável).
- **Sinais vitais** — PA como painel com componentes, peso, altura, temperatura, saturação,
  FC, FR, glicemia capilar, dor (EVA), perímetro cefálico com percentil. Validação de
  plausibilidade no servidor e no cliente (valor implausível é rejeitado com aviso).
- **Alergias estruturadas** — substância, reação, severidade, criticidade, status. Alerta no
  ato de prescrever substância conflitante, banner na capa.
- **Medicações ativas** — visão "medicamentos em uso agora" a um clique da consulta, com
  detecção de duplicidade.
- **Selo e versão** — profissional responsável + conselho; evolução emitida gera **versão
  imutável selada por hash**; edição cria nova versão (nada é sobrescrito em silêncio).
- **Continuidade** — taxonomia de tipo de atendimento, retorno agendado que vira
  `CalendarEvent`, encaminhamento registrado.

### Obstetrícia e enfermagem obstétrica (FExEO-SUS)

Episódio obstétrico completo, modelado a partir dos instrumentos do caderno
**FExEO-SUS / CEEO-Rede Alyne** (Ministério da Saúde + UFMG):

- **Gestação** — DUM, DPP, idade gestacional calculada, classificação de risco, histórico
  obstétrico (G/P/A), fatores de risco para pré-eclâmpsia, profilaxia com AAS.
- **Pré-natal** — visitas com exame físico dirigido, AU, BCF, apresentação, edema
  classificado, vacinas na gestação, orientações registradas.
- **Desfecho e recém-nascido** — tipo de parto, dados do RN (APGAR, peso, comprimento,
  perímetros, exame físico sistema por sistema, reflexos, eliminações, imunização BCG/HepB).
- **Enfermagem** — subcategorias parto / pós-parto / saúde sexual / geral, com dados
  estruturados por instrumento.

### Demais recursos clínicos

- **Documentos** — upload de PDF/imagem, pipeline de IA (OCR, classificação, extração),
  embeddings pgvector para RAG. IA **sugere**, o humano **confirma** — nada é gravado sem
  verificação.
- **Medições** — histórico com gráficos interativos, cada leitura com sua origem
  (consulta / documento / manual).
- **Exames** — resultados de laboratório, biópsias e outros, com tabelas estruturadas.
- **Imunizações** — vacinas com dados de lote/fabricante.
- **Antecedentes** — familiares por grau de parentesco, com condição associada.
- **Intercorrências** — eventos adversos (convulsões, quedas, reações alérgicas) com
  gatilhos suspeitos.
- **Diário de saúde** — registro do paciente: humor, dor, sono, adesão medicamentosa.

### Prescrição eletrônica

Prescrições via **Memed/SNCR**, com numeração SNCR e assinatura **ICP-Brasil**, armazenadas
com o PDF assinado. Alerta de alergia no momento de prescrever.

### Compartilhamento de dados

Um Coordenador abre uma **Finalidade de Compartilhamento** (ex.: estudo de epilepsia
coletando EEG); cada cuidador consente por arquivo, identificado ou anônimo. O consentimento
é registrado, congela quando o arquivo é compartilhado e pode ser revogado. Links externos
de documento têm escopo e expiração.

### Modelo de acesso

- **Admin** — administra a organização, usuários, licença. **Sem acesso clínico** por
  design (ADR 025).
- **Coordenador** — cadastra pacientes, delega acesso, gerencia grupos.
- **Cuidador** — cuida do dia a dia de pacientes específicos; é relação por paciente, não
  papel de sistema. Cobre família, enfermagem, responsável legal e qualquer um no círculo
  de cuidado. Vínculo legal é uma flag no grant (`is_legal_representative`, ADR 027).
- **Grupo** — conjunto nomeado de pacientes para gestão de acesso em bloco.

### Localização

Interface em **português, inglês e alemão**, com paridade de chaves nos três idiomas. Em
português as páginas legais são enquadradas em **LGPD / ANPD** (Lei 13.709/2018).

---

## Stack

| Camada | Tecnologia |
|---|---|
| Backend | FastAPI + uv (Python 3.12) |
| ORM | SQLAlchemy 2.0 async + asyncpg + Alembic |
| Auth | bcrypt + python-jose (JWT) + py_webauthn (passkeys) + next-auth v5 |
| Jobs | Celery + Redis |
| Frontend | Next.js 16 App Router + Tailwind CSS + shadcn/ui |
| i18n | next-intl (pt, en, de) — pt enquadrado em LGPD/ANPD |
| Banco | PostgreSQL 17 + pgvector (embeddings 768-dim HNSW) |
| IA | microsserviço FastAPI separado (Ollama / vLLM / Mistral / mock) |
| Proxy | Caddy (produção) |
| Mobile | Capacitor (shell sobre o frontend web — ADR 023) |

**Escala atual** (verificada no repositório): ~39 modelos-tabela · 34 routers ·
58 migrações Alembic · 47 páginas Next.js · suíte de testes com 567 testes verdes +
7 suítes Playwright E2E.

---

## Arquitetura

```
openavisio/
├── backend/          # FastAPI + SQLAlchemy + Celery
│   └── app/
│       ├── core/     # config, database, security, audit
│       ├── models/   # ORM — 39 arquivos de modelo
│       ├── schemas/  # DTOs Pydantic
│       ├── routers/  # 34 routers montados
│       ├── auth/     # RBAC — PatientAccessService
│       ├── workers/  # pipeline Celery + scheduler
│       └── deps.py   # DI: get_db, get_current_user, acesso a paciente
├── frontend/         # Next.js 16 App Router
│   └── src/
│       ├── app/      # 47 páginas (pacientes, família, obstetrícia, admin, auth)
│       ├── components/
│       ├── lib/      # api.ts — wrappers tipados da API
│       └── messages/ # i18n JSON (pt, en, de)
├── aiservice/        # FastAPI — OCR, classify, extract, embed, chat
├── mobile/           # shell Capacitor
└── deploy/           # compose dev/prod + Caddyfile
```

### Pipeline de documentos

Upload → criptografia (AES-256-GCM) → cadeia Celery:
1. **OCR** — Tesseract/OCRmyPDF + fallback de LLM de visão
2. **Classificação** — tipo de documento + emissor
3. **Extração** — entidades via LLM → armazenadas como JSONB
4. **Embedding** — chunks pgvector para RAG

O cuidador revisa o dado extraído → confirma → as entidades clínicas reais são criadas.

### Decisões de arquitetura

34 ADRs em `docs/adr/` documentam as decisões de fundo — do modelo de acesso à estratégia
de criptografia em repouso, passagem de autenticação com next-auth v5, criptografia
envelope por paciente com *crypto-shredding* (ADR 031), snapshot de release como base
limpa (ADR 032). Vale a leitura: é onde está o raciocínio, não só o código.

---

## Rodando

### Requisitos

- Docker + Docker Compose
- Node.js 22+ (frontend fora do Docker)
- Python 3.12 + [uv](https://docs.astral.sh/uv/) (backend fora do Docker)

### Subir a stack de desenvolvimento

```bash
cp .env.example .env
# Edite .env — defina APP_SECRET, POSTGRES_PASSWORD, etc.
# A IA é opcional: deixe OLLAMA_URL vazio para desligar, ou AI_BACKEND=mock para respostas prontas
docker compose -f deploy/docker-compose.dev.yml up
```

Serviços:

| Serviço | URL |
|---|---|
| Backend API | http://localhost:8000 (docs em `/docs`) |
| Frontend | http://localhost:3000 |
| Flower (Celery) | http://localhost:5555 |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

### Semear dados de desenvolvimento

```bash
curl -X POST http://localhost:8000/api/dev/seed
# Admin: admin@openavisio.dev / Admin123!Admin
```

### Desenvolvimento híbrido (recomendado)

Infra no Docker, código nativo — hot reload nativo e debugger, sem rebuilds.

```bash
docker compose -f deploy/docker-compose.infra.yml up -d
cd backend && uv sync && uv run alembic upgrade head && uv run uvicorn app.main:app --reload
# em outro terminal:
cd frontend && pnpm install && pnpm dev
```

Ver [`docs/adr/001-hybrid-local-dev.md`](docs/adr/001-hybrid-local-dev.md) e
[`docs/adr/002-devcontainer.md`](docs/adr/002-devcontainer.md) para o racional. O
devcontainer é suportado para quem prefere zero setup local.

### Testes

Os testes usam um banco separado, `vaultdb_test`. Crie uma vez:

```bash
docker compose -f deploy/docker-compose.infra.yml exec postgres \
  psql -U openavisio -d vaultdb -c "CREATE DATABASE vaultdb_test;"
docker compose -f deploy/docker-compose.infra.yml exec postgres \
  psql -U openavisio -d vaultdb_test -c "CREATE EXTENSION IF NOT EXISTS vector;"
```

```bash
cd backend
TEST_DATABASE_URL=postgresql+asyncpg://openavisio:devpassword123@localhost:5432/vaultdb_test \
  uv run pytest -v
```

A suíte exercita dois caminhos de schema: `create_all` (default) e migração Alembic
(`OA_TEST_SCHEMA=migrations`) — paridade migração↔modelo verificada por teste
(ADR/runbook em `docs/runbooks/migration-parity.md`).

---

## Deploy em produção

Clone, configure, suba:

```bash
cd /opt
git clone <seu-repo> openavisio
cd openavisio
./setup.sh --start
```

`setup.sh` verifica pré-requisitos, gera todos os segredos e faz algumas perguntas
(domínio/IP, backend de IA). A primeira visita ao domínio redireciona para `/setup`,
onde você cria a organização e a conta de admin.

### Requisitos de máquina

| | |
|---|---|
| SO | Ubuntu 22.04 / 24.04 ou Debian 12 |
| CPU | 2 núcleos mínimo |
| RAM | 4 GB mínimo (8 GB recomendado com Ollama local) |
| Disco | 20 GB mínimo |
| Docker | 24+ com o plugin Compose |
| LXC Proxmox | O container deve ser **privilegiado** — habilite **nesting** e **keyctl** em Container → Options → Features |

### IA local

O Ollama roda **fora** do Compose, para acessar a GPU diretamente. No Proxmox, rode no host:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Depois do primeiro login, configure em **Admin → Ollama / AI Backend** qual modelo serve
cada tarefa. Sem GPU, use `AI_BACKEND=mock` para exercitar o pipeline inteiro.

### Atualizando

```bash
git pull
docker compose pull
docker compose up -d --build
```

Migrações rodam automaticamente na inicialização do backend.

---

## Licença e atribuição

Distribuído sob **AGPL-3.0** (ver [`LICENSE`](LICENSE)).

Este projeto é derivado de um prontuário open-source publicado originalmente na Alemanha
(cuja base está preservada no histórico deste repositório sob os snapshots "public snapshot",
ADR 032). A camada clínica brasileira — endurecimento do prontuário (alergias estruturadas,
reconciliação de medicação, N diagnósticos, vitais ampliados, selo/versão da evolução,
imunizações, continuidade), obstetrícia e enfermagem obstétrica segundo os instrumentos
FExEO-SUS/CEEO-Rede Alyne, integração de prescrição eletrônica Memed/SNCR e o enquadramento
LGPD/ANPD — foi desenvolvida de forma independente.

Conforme a AGPL-3.0, o código-fonte completo está disponível neste repositório. Se você roda
uma instância modificada como serviço de rede, a licença exige que a fonte da sua versão
também esteja disponível aos usuários.
