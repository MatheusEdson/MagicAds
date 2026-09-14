<p align="center">
  <img src="assets/logo.svg" alt="MagicAds" width="420">
</p>

<p align="center">
  <b>Seu próprio app Meta, seu token, sua operação.</b><br>
  O que roda tráfego de verdade não é chat: é cron, payload fixo e conferência por <code>GET</code>.
</p>

<p align="center">
  <a href="https://github.com/MatheusEdson/MagicAds/actions/workflows/provas.yml"><img src="https://github.com/MatheusEdson/MagicAds/actions/workflows/provas.yml/badge.svg" alt="provas"></a>
  <img src="https://img.shields.io/badge/python-3.8%2B-blue" alt="python 3.8+">
  <img src="https://img.shields.io/badge/depend%C3%AAncias-0-brightgreen" alt="zero dependências">
  <img src="https://img.shields.io/badge/licen%C3%A7a-MIT-black" alt="MIT">
</p>

---

## O que é

MagicAds é o kit de quem opera Meta Ads com a **própria** conta de desenvolvedor, em vez de alugar a de um SaaS. São seis coisas num repo só:

| | |
|---|---|
| 🔑 **Guia do app Meta** | criar o app, escolher o caso de uso que **não** cai em App Review, e gerar o System User token que não expira |
| 🩺 **`diag`** | os 6 portões que fazem uma subida falhar, testados antes de você perder a tarde. Inclui o de WhatsApp, que **nenhuma leitura da API revela** |
| 🚀 **`subir`** | campanha + conjunto + criativo + anúncio a partir de um JSON. Ensaio por padrão, tudo nasce `PAUSED` |
| 📊 **ETL + `relatorio`** | métrica diária num Postgres seu, 4 tabelas, idempotente — e a leitura em formato de decisão, não de dashboard |
| 🧙 **Gandalf, o Dourado** | os agentes, **um por tipo de conta**: B2B, local, loja e balcão. Porque conselho médio em conta de pizzaria é conselho errado |
| 📜 **`contrato` + fluxos** | a ferramenta se descreve, e o agente sabe o que pode rodar sozinho. Sem isso ele inventa flag |

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

# 0. a trava que impede voce de empurrar segredo sem querer. Trinta segundos,
#    e e a unica protecao que roda ANTES do push (a CI so roda depois).
cp scripts/hooks/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push
cp .scrub-clientes.local.exemplo .scrub-clientes.local   # e ponha os seus clientes

# 1. cofre: um arquivo por cliente, 600
mkdir -p ~/.magicads/tokens
printf 'ACME_META_TOKEN=EAA...\n' > ~/.magicads/tokens/acme.env
chmod 600 ~/.magicads/tokens/acme.env

# 2. banco (Supabase OU Postgres seu)
export MAGICADS_SUPABASE_URL=https://xxxx.supabase.co
export MAGICADS_SUPABASE_KEY=...          # service key, só no servidor

# 3. confere cofre + banco + schema, e diz o que falta
python -m magicads init

# 4. a carteira mora no banco, não em arquivo versionado
python -m magicads cliente acme "Acme Pneus" --nicho auto --cidade "Sao Paulo"
python -m magicads conta acme meta act_000000000000000

# 5. dá pra subir? (os 6 portões)
python -m magicads diag acme
```

Sem dependência: só Python 3.8+ da biblioteca padrão. Não tem `pip install`, não tem `node_modules`, não tem framework. (Postgres seu em vez de Supabase? `DATABASE_URL` + `psycopg2`, e é a única dependência opcional do projeto.)

## O ciclo do dia

```bash
# subir: ENSAIO por padrão — imprime os 4 payloads e não chama a Meta
python -m magicads imagem acme act_000000000000000 criativo.jpg   # devolve imagem_hash
python -m magicads video  acme act_000000000000000 criativo.mp4   # devolve video_id
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
python -m magicads pausar acme --tudo     # FREIO GERAL: pausa tudo que está ativo
python -m magicads ativar acme 120xxxxxxxx --executar
```

`pausar --tudo` executa direto — digitar `--tudo` já é a confirmação, e freio que
pede confirmação em cima disso é freio que você não consegue usar às 23h. Ele tira
a lista de contas **da carteira**, nunca de `me/adaccounts`: o token quase sempre
enxerga conta de cliente vizinho, e pausar a campanha do vizinho é pior que o
problema que você estava resolvendo. Sem carteira, ele exige o `act_` na mão.
Não existe `ativar --tudo`.

`relatorio --mudas` sai com código 1 quando alguma conta **emudeceu** — dá pra pendurar no cron e só receber e-mail quando importa.

## As receitas

Subir na Graph são quatro chamadas encadeadas, cada uma com campo obrigatório que a Meta só reclama depois, com mensagem que não diz o que faltou. A receita é um JSON com **o que muda**; o resto é trabalho do código.

| Receita | Tipo de conta | Destino | A armadilha que ela evita |
|---|---|---|---|
| [`b2b-formulario.json`](receitas/b2b-formulario.json) | B2B, alto ticket | formulário instantâneo | `advantage_audience:1` em público pequeno torna sua demografia **decorativa** |
| [`local-whatsapp.json`](receitas/local-whatsapp.json) | serviço local | conversa no WhatsApp | o número **não vai no criativo**: mora no `promoted_object` |
| [`loja-conversao.json`](receitas/loja-conversao.json) | loja, e-commerce | site + pixel | aquisição que não exclui quem já comprou chama isso de ROAS |
| [`balcao-trafego.json`](receitas/balcao-trafego.json) | balcão, delivery | site | otimizar por evento que quase não dispara trava no aprendizado pra sempre |
| [`loja-video-reels.json`](receitas/loja-video-reels.json) | loja, criativo em vídeo | Reels e Stories | vídeo sem `capa_hash` deixa a Meta sortear o frame, e o sorteado costuma ser a pessoa de olho fechado |

Cada uma valida antes de sair da sua máquina: verba em centavos abaixo do mínimo, falta de geografia, `promoted_object` ausente e criativo sem imagem **param aqui**, de graça.

## O que cada plataforma deixa fazer

Antes de promessa, a verdade. Esta tabela existe para ninguém — pessoa ou agente — prometer o que não tem API:

| Plataforma | Ler | Subir | Pausar | Como |
|---|---|---|---|---|
| **Meta** | ✅ | ✅ | ✅ | `magicads` ponta a ponta |
| **Instagram** | ✅ | ✅ | ✅ | **é posicionamento, não canal separado** |
| **Google Ads** | ✅ no ETL | ❌ | ❌ | subida é na interface, hoje |
| **Google Business** | ⚠️ parcial | ❌ | ❌ | **não existe API de produto.** A ficha é na mão |
| **LinkedIn** | ❌ | ❌ | ❌ | API separada, ainda não integrada |

Instagram não é canal a mais: é uma linha no targeting (`posicionamentos`) mais o `instagram_id` — sem ele o anúncio roda no IG com o nome e a foto da **Página do Facebook**. Tratar como canal separado leva a campanha duplicada e verba dividida entre duas coisas que a Meta já otimizava junto.

Google Business não tem endpoint de produto, e termo novo na ficha demora da ordem de **dois meses** para aparecer. Ficha é trabalho de mês, e medir mudança dela em sete dias não mede nada. Detalhe em [`aios/fluxos/`](aios/fluxos/).

## Os agentes sabem o que rodar

Um agente com doutrina e sem contrato inventa flag. Por isso a ferramenta **se descreve**:

```bash
python -m magicads contrato          # o que existe nesta versão, e o portão de cada comando
python -m magicads contrato --json   # para ferramenta
```

Quatro portões, e é o que decide se o agente age ou propõe:

| Portão | O agente | Comandos |
|---|---|---|
| `LIVRE` | roda à vontade | `contrato`, `init`, `clientes`, `diag`, `get`, `etl`, `relatorio` |
| `ESCREVE` | roda e conta depois | `imagem`, `video` |
| `FREIO` | em emergência roda sozinho e avisa **depois** | `pausar` |
| `HUMANO` | **nunca** roda: monta, mostra, espera | `subir --executar`, `ativar`, `post --executar` |

O ofício — o que fazer, em que ordem — mora em [`aios/fluxos/`](aios/fluxos/): subir, operar, emergência, e um arquivo por plataforma. E `tests/test_agentes.py` falha se um agente citar comando que não existe ou apontar para um fluxo apagado, então isso não depende de ninguém lembrar.

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
6. `./scripts/scrub.sh` antes de todo push, e tem hook em `scripts/hooks/pre-push` pra não depender da sua memória. `./scripts/historico.sh` varre o **histórico inteiro**, que é outra pergunta: segredo que entrou num commit e saiu no seguinte some da árvore e continua no pack.

```bash
python -m unittest discover -s tests   # 116 testes, stdlib, sem instalar nada
./scripts/scrub.sh
```

As três coisas rodam sozinhas a cada push (`.github/workflows/provas.yml`):
testes em Python 3.8 e 3.12, Linux e Windows · o scrub · e o **ensaio de cada
receita de exemplo**, porque exemplo quebrado é pior que exemplo ausente — quem
copia não desconfia.

## Estado

| Parte | Estado |
|---|---|
| `init`, `cliente`, `conta` — a carteira | ✅ funciona |
| `diag` — os 6 portões | ✅ funciona, **provado em conta real** |
| `subir` + receitas por tipo de conta | ✅ funciona, **provado em conta real** (campanha criada, conferida e apagada) |
| `get`, `post`, `pausar`, `ativar`, `imagem` | ✅ funciona |
| `remover` — apaga e prova por GET | ✅ funciona, **provado em conta real** |
| `pausar --tudo` — freio geral | ✅ funciona |
| `contrato` + fluxos por plataforma | ✅ pronto |
| Vídeo e posicionamento no `subir` | ✅ funciona |
| ETL Meta + Google, idempotente | ✅ funciona, **provado gravando em Postgres real** (3 rodadas, 16 linhas, sem duplicar) |
| `relatorio` — portfólio, campanha, mudas | ✅ funciona, **lido do banco de verdade** |
| Agentes Gandalf, 4 tipos de conta + porteiro | ✅ prontos |
| Instagram | ✅ **não era canal, era posicionamento** — já sobe |
| Google Ads: subir pela API | 🚧 depois (hoje lê; subir é na interface) |
| GBP | ⛔ **não tem API de produto.** Fluxo escrito, automação não existe |
| LinkedIn | 🚧 depois (API separada, coletor novo) |
| Quebra por posicionamento no ETL | 🚧 depois |

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
