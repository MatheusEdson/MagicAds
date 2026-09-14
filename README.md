<p align="center">
  <img src="assets/logo.svg" alt="MagicAds" width="420">
</p>

<p align="center">
  <b>Seu próprio app Meta, seu token, sua operação.</b><br>
  O que roda tráfego de verdade não é chat: é cron, payload fixo e conferência por <code>GET</code>.
</p>

---

## O que é

MagicAds é o kit de quem opera Meta Ads com a **própria** conta de desenvolvedor, em vez de alugar a de um SaaS. São cinco coisas num repo só:

| | |
|---|---|
| 🔑 **Guia do app Meta** | criar o app, escolher o caso de uso que **não** cai em App Review, e gerar o System User token que não expira |
| 🩺 **`diag`** | os 6 portões que fazem uma subida falhar, testados antes de você perder a tarde. Inclui o de WhatsApp, que **nenhuma leitura da API revela** |
| 🚀 **`subir`** | campanha + conjunto + criativo + anúncio a partir de um JSON. Ensaio por padrão, tudo nasce `PAUSED` |
| 📊 **ETL + `relatorio`** | métrica diária num Postgres seu, 4 tabelas, idempotente — e a leitura em formato de decisão, não de dashboard |
| 🧙 **Gandalf, o Dourado** | os agentes, **um por tipo de conta**: B2B, local, loja e balcão. Porque conselho médio em conta de pizzaria é conselho errado |

## Por que não usar só o MCP oficial

O MCP de ads da Meta (29 ferramentas, aberto em 29/04/2026) é excelente pra perguntar coisa no chat. Ele não sustenta uma operação:

| | MCP oficial | MagicAds |
|---|---|---|
| Roda em cron, sem ninguém na frente | **não**, é sessão de chat | sim |
| Custo de contexto | ~134k tokens só pras definições | zero |
| Quem monta o payload | o modelo | a receita, sempre igual |
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

# 2. banco (Supabase ou Postgres seu)
export MAGICADS_SUPABASE_URL=https://xxxx.supabase.co
export MAGICADS_SUPABASE_KEY=...          # service key, só no servidor

# 3. confere cofre + banco + schema, e diz o que falta
python -m magicads init

# 4. a carteira mora no banco, não em arquivo versionado
python -m magicads cliente acme "Acme Pneus" --nicho auto --cidade Uberlandia
python -m magicads conta acme meta act_000000000000000

# 5. dá pra subir? (os 6 portões)
python -m magicads diag acme
```

Sem dependência: só Python 3.8+ da biblioteca padrão. Não tem `pip install`, não tem `node_modules`, não tem framework. (Postgres seu em vez de Supabase? `DATABASE_URL` + `psycopg2`, e é a única dependência opcional do projeto.)

## O ciclo do dia

```bash
# subir: ENSAIO por padrão — imprime os 4 payloads e não chama a Meta
python -m magicads imagem acme act_000000000000000 criativo.jpg   # devolve o hash
python -m magicads subir receitas/local-whatsapp.json
python -m magicads subir receitas/local-whatsapp.json --executar   # cria, tudo PAUSED

# encher a série (idempotente: pode rodar quantas vezes quiser no mesmo dia)
python -m magicads etl --dias 7 --seco    # mostra e não escreve
python -m magicads etl --dias 7

# ler a série, em formato de decisão
python -m magicads relatorio              # portfólio + Δ vs janela anterior
python -m magicads relatorio acme --dias 14   # ontem vs a média da própria campanha
python -m magicads relatorio --mudas      # quem parou de reportar

# freio e acelerador
python -m magicads pausar acme 120xxxxxxxx
python -m magicads ativar acme 120xxxxxxxx --executar
```

`relatorio --mudas` sai com código 1 quando alguma conta **emudeceu** — dá pra pendurar no cron e só receber e-mail quando importa.

## As receitas

Subir na Graph são quatro chamadas encadeadas, cada uma com campo obrigatório que a Meta só reclama depois, com mensagem que não diz o que faltou. A receita é um JSON com **o que muda**; o resto é trabalho do código.

| Receita | Tipo de conta | Destino | A armadilha que ela evita |
|---|---|---|---|
| [`b2b-formulario.json`](receitas/b2b-formulario.json) | B2B, alto ticket | formulário instantâneo | `advantage_audience:1` em público pequeno torna sua demografia **decorativa** |
| [`local-whatsapp.json`](receitas/local-whatsapp.json) | serviço local | conversa no WhatsApp | o número **não vai no criativo**: mora no `promoted_object` |
| [`loja-conversao.json`](receitas/loja-conversao.json) | loja, e-commerce | site + pixel | aquisição que não exclui quem já comprou chama isso de ROAS |
| [`balcao-trafego.json`](receitas/balcao-trafego.json) | balcão, delivery | site | otimizar por evento que quase não dispara trava no aprendizado pra sempre |

Cada uma valida antes de sair da sua máquina: verba em centavos abaixo do mínimo, falta de geografia, `promoted_object` ausente e criativo sem imagem **param aqui**, de graça.

## A ordem importa

Fazer fora de ordem é o que custa o dia:

1. [`docs/01-app-meta.md`](docs/01-app-meta.md) — o app, e o caso de uso que evita App Review
2. [`docs/02-token.md`](docs/02-token.md) — System User, escopos, expiração "Nunca", cofre
3. `python -m magicads init` e depois `diag <cliente>` até dar **PODE SUBIR**
4. [`db/schema.sql`](db/schema.sql) — 4 tabelas, e o ETL tem onde escrever
5. o agente, que só faz sentido quando já existe série no banco

📐 **[`docs/ARQUITETURA.md`](docs/ARQUITETURA.md)** tem os diagramas de o que conecta onde. Se for ler um arquivo só, leia esse.

## O que este repo NÃO faz

Dito na cara, pra ninguém perder tempo:

- **não decide por você.** Ele executa o que você mandou, e ensaia antes de criar
- **não é dashboard.** O banco existe pra ter série comparável, não pra ter gráfico
- **não sobe campanha ligada.** Não tem flag pra isso. Revisar antes de gastar é a diferença entre erro barato e erro caro
- **não resolve o que é do cliente.** Forma de pagamento, papel na conta e WhatsApp conectado na Página são ações dele. O `diag` diz qual é qual, e aí você manda a lista pronta
- **não te livra da Verificação da Empresa** se você quiser `leads_retrieval` e os tiers mais altos. O caminho do MVP contorna isso; os formulários instantâneos, não

## Segurança

Detalhe em [SECURITY.md](SECURITY.md). O resumo:

1. O token **nunca** é impresso. O filtro de saída troca o valor por `<SEGREDO>` inclusive dentro de mensagem de erro (a Meta ecoa parâmetro, e é assim que token vaza em log). E o filtro é **um só**, em `magicads/comum.py`: dois filtros não são redundância, são a chance de um ficar pra trás.
2. `post` roda em **modo validação por padrão** e `subir` em **modo ensaio**. Criar de verdade exige `--executar`.
3. ⚠️ **`validate_only` não protege em `/campaigns`.** A Meta cria de verdade nesse endpoint, com ou sem a flag. Em conjunto e anúncio, protege. O `subir` ensaia o conjunto antes de valer, e avisa na hora.
4. Cofre com um arquivo por cliente, `chmod 600`. Perder um não é perder todos.
5. **Falha não vira zero.** Se a conta falhar no ETL, nada é escrito pra ela: zero por erro de rede vira "a campanha parou" no relatório.
6. `./scripts/scrub.sh` antes de todo push, e tem hook em `scripts/hooks/pre-push` pra não depender da sua memória.

```bash
python -m unittest discover -s tests   # 55 testes, stdlib, sem instalar nada
./scripts/scrub.sh
```

## Estado

| Parte | Estado |
|---|---|
| `init`, `cliente`, `conta` — a carteira | ✅ funciona |
| `diag` — os 6 portões | ✅ funciona |
| `subir` + receitas por tipo de conta | ✅ funciona |
| `get`, `post`, `pausar`, `ativar`, `imagem` | ✅ funciona |
| ETL Meta + Google, idempotente | ✅ funciona |
| `relatorio` — portfólio, campanha, mudas | ✅ funciona |
| Agentes Gandalf, 4 tipos de conta + porteiro | ✅ prontos |
| Instagram, GBP, LinkedIn | 🚧 depois (mesmo formato, é somar canal) |
| Vídeo no `subir` (hoje só imagem) | 🚧 depois |

## Os agentes

**Gandalf, o Dourado**, separado por tipo de conta, em [`aios/agents/`](aios/agents/):

| Agente | Tipo de conta | Ciclo | Métrica que manda | Receita |
|---|---|---|---|---|
| `gandalf` 🧙 | porteiro, classifica e encaminha | — | — | — |
| `gandalf-b2b` | B2B, alto ticket | semanas a meses | custo por reunião | `b2b-formulario.json` |
| `gandalf-local` | serviço local | dias | custo por agendamento | `local-whatsapp.json` |
| `gandalf-loja` | loja, e-commerce | horas a dias | ROAS, custo por compra | `loja-conversao.json` |
| `gandalf-balcao` | balcão, delivery | minutos | custo por pedido, alcance | `balcao-trafego.json` |

Tipo de conta decide objetivo, evento de otimização, métrica e criativo. Um agente genérico dá conselho médio, e conselho médio numa pizzaria é conselho errado: pizzaria não tem funil de lead, tem pedido e recorrência.

## Licença

MIT. Ver [LICENSE](LICENSE). Mudanças em [CHANGELOG.md](CHANGELOG.md).
