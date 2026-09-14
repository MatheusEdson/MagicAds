<p align="center">
  <img src="assets/logo.svg" alt="MagicAds" width="420">
</p>

<p align="center">
  <b>Seu próprio app Meta, seu token, sua operação.</b><br>
  O que roda tráfego de verdade não é chat: é cron, payload fixo e conferência por <code>GET</code>.
</p>

---

## O que é

MagicAds é o kit de quem opera Meta Ads com a **própria** conta de desenvolvedor, em vez de alugar a de um SaaS. São quatro coisas num repo só:

| | |
|---|---|
| 🔑 **Guia do app Meta** | criar o app, escolher o caso de uso que **não** cai em App Review, e gerar o System User token que não expira |
| 🩺 **`diag`** | os 6 portões que fazem uma subida falhar, testados antes de você perder a tarde. Inclui o de WhatsApp, que **nenhuma leitura da API revela** |
| ⚙️ **CLI** | subir, suspender e consultar pela Graph API, com validação por padrão e token que nunca aparece na saída |
| 📊 **ETL + banco** | métrica diária num Postgres seu, 4 tabelas, idempotente |
| 🧙 **Gandalf, o Dourado** | os agentes, **um por tipo de conta**: B2B, local, loja e balcão. Porque conselho médio em conta de pizzaria é conselho errado |

## Por que não usar só o MCP oficial

O MCP de ads da Meta (29 ferramentas, aberto em 29/04/2026) é excelente pra perguntar coisa no chat. Ele não sustenta uma operação:

| | MCP oficial | MagicAds |
|---|---|---|
| Roda em cron, sem ninguém na frente | **não**, é sessão de chat | sim |
| Custo de contexto | ~134k tokens só pras definições | zero |
| Quem monta o payload | o modelo | você |
| Custom Audiences e Lookalike | não cobre | cobre |
| Conta fora do seu portfólio | lê pela metade, e às vezes **devolve lista vazia no lugar de erro** | o token certo enxerga, e o `diag` prova qual é |

> **Lista vazia com HTTP 200 não é "não tem", é "não vejo".** Metade dos bugs de integração com a Meta é isso.

## Começando

```bash
git clone https://github.com/MatheusEdson/MagicAds
cd MagicAds

# 1. cofre: um arquivo por cliente, 600
mkdir -p ~/.magicads/tokens
printf 'ACME_META_TOKEN=EAA...\n' > ~/.magicads/tokens/acme.env
chmod 600 ~/.magicads/tokens/acme.env

# 2. o token abre? quais contas ele enxerga?
python -m magicads clientes

# 3. dá pra subir? (os 6 portões)
python -m magicads diag acme

# 4. consultar
python -m magicads get acme act_000000000000000/campaigns fields=name,status,objective

# 5. subir (valida primeiro, cria só com --executar)
python -m magicads post acme act_000000000000000/campaigns \
  name="[C01] teste" objective=OUTCOME_LEADS status=PAUSED \
  special_ad_categories="[]"

# 6. freio
python -m magicads pausar acme 120000000000000000

# 7. série no banco (Meta + Google), idempotente
export MAGICADS_SUPABASE_URL=https://xxxx.supabase.co
export MAGICADS_SUPABASE_KEY=...          # service key, só no servidor
python -m magicads etl --dias 7 --seco    # mostra e não escreve
python -m magicads etl --dias 7
```

Sem dependência: só Python 3.8+ da biblioteca padrão. Não tem `pip install`, não tem `node_modules`, não tem framework. (Postgres seu em vez de Supabase? `DATABASE_URL` + `psycopg2`, e é a única dependência opcional do projeto.)

## A ordem importa

Fazer fora de ordem é o que custa o dia:

1. [`docs/01-app-meta.md`](docs/01-app-meta.md) — o app, e o caso de uso que evita App Review
2. [`docs/02-token.md`](docs/02-token.md) — System User, escopos, expiração "Nunca", cofre
3. `python -m magicads diag <cliente>` até dar **PODE SUBIR**
4. [`db/schema.sql`](db/schema.sql) — 4 tabelas, e o ETL tem onde escrever
5. o agente, que só faz sentido quando já existe série no banco

📐 **[`docs/ARQUITETURA.md`](docs/ARQUITETURA.md)** tem os diagramas de o que conecta onde. Se for ler um arquivo só, leia esse.

## O que este repo NÃO faz

Dito na cara, pra ninguém perder tempo:

- **não decide por você.** Ele executa o que você mandou, e pergunta antes de criar
- **não é dashboard.** O banco existe pra ter série comparável, não pra ter gráfico
- **não resolve o que é do cliente.** Forma de pagamento, papel na conta e WhatsApp conectado na Página são ações dele. O `diag` diz qual é qual, e aí você manda a lista pronta
- **não te livra da Verificação da Empresa** se você quiser `leads_retrieval` e os tiers mais altos. O caminho do MVP contorna isso; os formulários instantâneos, não

## Segurança

Detalhe em [SECURITY.md](SECURITY.md). O resumo:

1. O token **nunca** é impresso. O filtro de saída troca o valor por `<TOKEN>` inclusive dentro de mensagem de erro (a Meta ecoa parâmetro, e é assim que token vaza em log).
2. `post` roda em **modo validação por padrão**. Criar de verdade exige `--executar`.
3. ⚠️ **`validate_only` não protege em `/campaigns`.** A Meta cria de verdade nesse endpoint, com ou sem a flag. Em conjunto e anúncio, protege. O CLI avisa na hora.
4. Cofre com um arquivo por cliente, `chmod 600`. Perder um não é perder todos.
5. **Falha não vira zero.** Se a conta falhar no ETL, nada é escrito pra ela: zero por erro de rede vira "a campanha parou" no relatório.
6. `./scripts/scrub.sh` antes de todo push, e tem hook em `scripts/hooks/pre-push` pra não depender da sua memória.

## Estado

| Parte | Estado |
|---|---|
| CLI (`clientes`, `diag`, `get`, `post`, `pausar`, `ativar`) | ✅ funciona |
| ETL Meta + Google, idempotente | ✅ funciona |
| Schema do banco (4 tabelas) | ✅ pronto |
| Guias do app Meta e do token | ✅ escritos |
| Agentes Gandalf, 4 tipos de conta + porteiro | ✅ prontos |
| Instagram, GBP, LinkedIn | 🚧 depois (mesmo formato, é somar canal) |

## Os agentes

**Gandalf, o Dourado**, separado por tipo de conta, em [`aios/agents/`](aios/agents/):

| Agente | Tipo de conta | Ciclo | Métrica que manda |
|---|---|---|---|
| `gandalf` 🧙 | porteiro, classifica e encaminha | — | — |
| `gandalf-b2b` | B2B, alto ticket | semanas a meses | custo por reunião |
| `gandalf-local` | serviço local | dias | custo por agendamento |
| `gandalf-loja` | loja, e-commerce | horas a dias | ROAS, custo por compra |
| `gandalf-balcao` | balcão, delivery | minutos | custo por pedido, alcance |

Tipo de conta decide objetivo, evento de otimização, métrica e criativo. Um agente genérico dá conselho médio, e conselho médio numa pizzaria é conselho errado: pizzaria não tem funil de lead, tem pedido e recorrência.

## Licença

MIT. Ver [LICENSE](LICENSE).
