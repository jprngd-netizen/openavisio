# Plano de implementação — Parte B: Interação medicamentosa (R3-B)

> Fundado na pesquisa `docs/research/2026-10-10-drug-interaction.md` e nas decisões DEC-2b (base externa)
> e IX-DEC-1/2 (fechadas pela pesquisa). Repo `/home/ubuntu/openavisio`. Não executa nada por si.

## Contexto

O app já tem o **list de medicações ativas** (`WS-2`/`medication_reconciliation`) e prescrições via Memed.
Falta alertar sobre **interações fármaco–fármaco**. Restrições inegociáveis: **nenhuma PHI sai** (só
nome/código de fármaco), **advisory** (nunca bloqueia), **degradação silenciosa**.

## Achados da pesquisa que definem o desenho

- **DDI API do RxNav/RxNorm foi DESCONTINUADA (02/01/2024)** → não é fonte. RxNorm só serve para
  **normalização** (nome→RxCUI), e é US-centric para nomes comerciais brasileiros.
- **DrugBank** só em licença paga → descartado.
- **Memed** já mostra alerta de interação **no próprio iframe** (leve/moderado/grave), mas é client-side
  cross-origin — **não legível por API**. → é **camada humana** (grátis), não reimplementar.
- **IMSES/CRF-MG** (base BR, ~330 interações graves, PT) tem **API grátis mas exige chave**.
- **DDInter 2.0** (CC BY-NC-SA, ~302k DDI, ATC) permite **uso offline** → melhor **fallback sempre-on**.
- Mapear texto-livre PT → **princípio ativo** via **dados abertos ANVISA** + dicionário de sinônimos.

## MVP — decisão do owner (2026-10-10)

**Para o MVP, a checagem de interação vai pela própria Memed.** O módulo de prescrição da Memed já
exibe o alerta de interação (leve/moderado/grave); o app **não** constrói base própria nesta fase.
Consequências: **IX-1..IX-4 ficam para o pós-MVP (backlog)**, e o MVP entrega apenas (a) o
realce/documentação do que a Memed já faz e (b) um aviso honesto na UI: a checagem ocorre **no fluxo
Memed** e **medicação em texto livre fora do Memed não é checada automaticamente** (limitação conhecida).
Nota: o alerta da Memed considera o que está na sessão Memed; a lista livre do app não entra nele.

## Decisões de engenharia (Senna, 2026-10-10)

1. **Fonte primária do app = DDInter 2.0 local** (offline, sem chave, sem PHI). **IMSES fica opcional**
   (camada extra, só com chave) — não bloqueia a Parte B.
2. **Camada humana = alerta nativo da Memed** (já existe) — não reimplementar; apenas documentar/realçar.
3. **Dataset NÃO versionado no repo** (licença NC do DDInter + tamanho): baixado por
   `scripts/fetch_interaction_data.py` para `data/interactions/` (gitignored) e carregado no startup.
   ANVISA (dados abertos, redistribuível) segue o mesmo caminho por uniformidade.
4. **Severidade por padrão = só grave/major** em destaque; moderado discreto; leve/unknown oculto.
5. **Feature flag** desligada por padrão; ligar só para o Gabriel primeiro.

## Workstreams

| ID | Entrega | Depende | Gate |
|----|---------|---------|------|
| IX-1 | **Mapeamento** texto-livre PT → princípio(s) ativo(s) (normalização + decomposição de associações + sinônimos PT↔INN). Serviço + índice a partir do dataset ANVISA | — | cobertura medida sobre o catálogo real; casos "Neosaldina→dipirona", "AAS→ácido acetilsalicílico" |
| IX-2 | **Base de interação local** (DDInter) + `drug_interaction_cache` por par + `InteractionService.check(list[ativo]) -> Alert[]` | IX-1 | pares sabidamente graves retornam correto; cache hit |
| IX-3 | **Alerta advisory** na UI, atrás de flag; só grave destacado; "não substitui avaliação clínica" | IX-2 | par interagente mostra aviso; par sem interação não mostra |
| IX-4 | **Degradação + observabilidade**: timeout curto, circuito `fonte→cache`, `status=unavailable` sem travar prescrição | IX-2/3 | fonte/dataset ausente não altera o fluxo |
| IX-5 (depois) | **Camada IMSES** (exige chave) + realce do alerta nativo Memed | IX-2 | pendente de credencial |

## Regras transversais

- **Nunca** enviar PHI: `check()` recebe só códigos/nomes de ativos.
- Cache com **TTL longo (30–90 d)** por par ordenado.
- **Nunca bloquear** prescrição/fluxo Memed; ausência de alerta ≠ ausência de interação (exibir no rodapé).
- Licença: DDInter é **não-comercial** — ok uso pessoal/familiar; revisitar antes de qualquer distribuição.

## Sequência e rollout

Serie (schema + working tree compartilhados): **IX-1 → IX-2 → IX-3 → IX-4**. Schema aditivo; rollback =
desligar a flag (nenhum dado clínico depende da fonte). Testes com fixtures offline (sem rede no CI) +
um teste `skipif` de integração real.

## Verificação (por workstream)

Suíte pytest verde (baseline **502**), head Alembic único, `tsc --noEmit` exit 0, paridade i18n pt/en/de.
Cada WS entrega commits atômicos, branch própria, e reporta SHAs + resultado literal.

---

*Implementação/QA/release seguem skills próprias. Onde há "modelo proposto" é engenharia, não guideline clínico.*
