# Changelog

## 1.3.0 — 2026-09-14

Primeira rodada **contra conta real** (22 contas, só leitura). Achou dois bugs
que nenhum teste com API de mentira acharia, porque os dois dependem do formato
que a Meta devolve de verdade.

### Corrigido

- **O ETL contava o mesmo lead duas vezes.** A Meta reporta o mesmo resultado em
  mais de um `action_type`: `lead` é o total de Leads e **já inclui** o do pixel
  e o do formulário. O parser somava os três.
  - Visto ao vivo: uma linha com `lead=1` e
    `offsite_conversion.fb_pixel_lead=1` — o mesmo lead, contado como dois.
  - É o jeito mais caro de errar: resultado inflado **divide o custo**, então um
    lead de R$ 100 aparece como dois de R$ 50 e você escala o que não estava
    funcionando. Na conta testada, o custo por resultado dobrou depois do
    conserto.
  - Agora existem **famílias**: dentro de cada uma o agregado manda e os
    específicos só entram se ele não veio; entre famílias (lead × compra) soma
    normal. Cinco testes de regressão, incluindo o caso real.

- **O `diag` dava "página FALTA" com dez páginas na mão.** Ele lia página só
  pelas bordas do portfólio (`owned_pages`/`client_pages`). Um system user que
  opera o BM do *cliente* sem ser admin de lá recebe **lista vazia** nessas
  bordas — 200 com `data:[]`, não erro. Ao vivo: 28 bordas devolveram zero
  enquanto `me/assigned_pages` devolvia 10 páginas usáveis. Agora usa as duas
  fontes, deduplica, e diz de onde veio cada uma.

### Mudou

- **O veredito do `diag` agora conta.** Com token de frota, "forma de pagamento:
  OK" bastava **uma** conta ter forma de pagamento para a linha ficar verde. Na
  conta real isso escondia que só **11 de 22** estavam prontas para subir. As
  linhas passam a mostrar `OK (11 de 22)` e há uma linha própria de
  `contas prontas p/ subir`.
- A sonda de WhatsApp agora escolhe uma página **com `MESSAGING`** e uma conta
  que realmente pode criar. Pendurada na página errada, ela devolvia outro erro
  e você concluía a coisa errada sobre o WhatsApp.
- 93 testes (eram 88).

## 1.2.0 — 2026-09-14

O elo que faltava: os agentes tinham **doutrina** e nenhum **contrato com a
ferramenta**. Sabiam o que aconselhar e não sabiam o que rodar — e por isso
inventariam flag e prometeriam automação onde não existe API.

### Novo

- **`magicads contrato`** — a ferramenta se descreve. Lista real dos comandos
  daquela versão, com **o portão de cada um**: `LIVRE` (roda à vontade),
  `ESCREVE` (roda e conta depois), `FREIO` (em emergência roda sozinho e avisa
  depois), `HUMANO` (nunca roda: monta, mostra, espera). `--json` para
  ferramenta. Uma lista escrita à mão divergiria do código no primeiro commit,
  e aí o agente passaria a mentir com mais confiança.
- **`aios/fluxos/`** — o ofício: `meta-subir`, `meta-operar`, `meta-emergencia`,
  e um arquivo por plataforma. O `README.md` de lá é **a matriz honesta do que
  cada plataforma deixa fazer**, que é o que impede o agente de prometer o
  impossível.
- **`magicads video`** — sobe vídeo para a biblioteca da conta (multipart, sem
  dependência nova). O `subir` aceita `video_id` + `capa_hash`. Vídeo sem capa
  faz a Meta sortear um frame, e frame sorteado de vídeo vertical costuma ser a
  pessoa de olho fechado — por isso a receita exige.
- **Posicionamento e Instagram no `subir`**: `posicionamentos`,
  `posicoes_instagram`, `posicoes_facebook` e `instagram_id`. Sem declarar
  posicionamento, a Meta vai buscar volume barato em Audience Network; sem
  `instagram_id`, o anúncio roda no IG com a identidade da Página do Facebook.
- **`receitas/loja-video-reels.json`** — a quinta receita, mostrando as três
  peças que só aparecem em vídeo.
- **`tests/test_agentes.py`** — falha se um agente ou fluxo citar comando que
  não existe, apontar para arquivo apagado, ou pedir receita que sumiu. E
  valida o bloco YAML de cada agente (job próprio na CI, com PyYAML instalado
  só lá — o MagicAds continua sem dependência).
- 88 testes (eram 60).

### Corrigido

- **O bloco YAML de dois agentes não era YAML válido**: `description: Monta a
  semana: picos...` tem dois `:` e o parser para no primeiro.
  - Para ser justo com o tamanho do problema: hoje **ninguém parseia esse
    bloco**. No Claude Code o `.md` inteiro vira prompt e o modelo lê como
    texto, então as regras continuavam valendo. O bloco inválido não estava
    apagando nada.
  - Vale arrumar mesmo assim, por dois motivos: um bloco que se anuncia como
    `yaml` e não é vira uma armadilha para a primeira ferramenta que tentar lê-lo
    (um índice, um manifest, um verificador de portões), e ela vai falhar ou
    pular em silêncio. E os testes de conteúdo — id bate com o arquivo, todos se
    chamam Gandalf, todos conhecem os portões — precisam de um parse para
    existir.

### Mudou

- Instagram sai de "🚧 depois" para **feito**: ele nunca foi um canal a mais, é
  posicionamento da mesma campanha. Tratar como canal separado levaria a
  campanha duplicada e verba dividida entre duas coisas que a Meta já otimizava
  junto.
- GBP sai de "🚧 depois" para **⛔ não tem API de produto**. O fluxo está
  escrito; a automação não existe, e prometer que existe seria o pior erro do
  pacote.

## 1.1.0 — 2026-09-14

### Novo

- **`pausar <cliente> --tudo`** — o freio geral. Pausa toda campanha ativa das
  contas do cliente e **executa direto**: digitar `--tudo` já é a confirmação, e
  freio que pede confirmação em cima disso é freio que você não consegue usar
  às 23h. A lista de contas sai da **carteira**, nunca de `me/adaccounts` — o
  token quase sempre enxerga conta de cliente vizinho, e pausar a campanha do
  vizinho é pior que o problema que você estava resolvendo. Sem carteira, exige
  o `act_` na mão. Confere cada uma por `GET` no próprio id e denuncia quem a
  Meta aceitou e não aplicou. Não existe `ativar --tudo`.
  - Lista vazia não é declarada como "nada ativo": `data:[]` com HTTP 200 é
    também o que a Meta devolve sob rate limit, e dizer "tudo certo" aí é mandar
    a pessoa dormir com a conta gastando.
- **CI** (`.github/workflows/provas.yml`): testes em Python 3.8 e 3.12, Linux e
  Windows · o scrub · e o **ensaio de cada receita de exemplo**. O hook de
  pre-push depende de quem clonou ter instalado; quem forka não instala, e aí a
  promessa de "nenhum segredo no repo" valia só na máquina de um.
- 60 testes (eram 55).

### Mudou

- **Nova marca: chapéu de mago**, estilo quadrinho, em ouro — casa com *Gandalf,
  o Dourado* de um jeito que a varinha não casava. `logo.svg` e `mark.svg`
  compartilham a mesma geometria em vez de duas cópias, porque duas cópias
  divergem no primeiro retoque. Legível até 32px.

## 1.0.0 — 2026-09-14

A v0 era biblioteca: dava pra ler a API, mas não dava pra **operar**. Faltavam
as três peças que fecham o ciclo — cadastrar a carteira, subir campanha sem
montar payload na mão, e ler o que o ETL gravou.

### Novo

- **`subir <receita.json>`** — campanha + conjunto + criativo + anúncio a partir
  de um JSON. Modo **ensaio por padrão** (imprime os quatro payloads e não chama
  a Meta); criar de verdade exige `--executar`. Tudo nasce `PAUSED`, e não existe
  opção de subir ligado. Se falhar no meio, imprime o que já foi criado e o
  comando exato pra remover.
- **`receitas/*.json`** — uma por tipo de conta (B2B, local/WhatsApp, loja,
  balcão), casadas com os agentes Gandalf. Cada uma carrega, em `_atencao`, a
  armadilha específica daquele tipo.
- **`relatorio`** — a leitura que faltava, em três perguntas: portfólio (com Δ
  contra a janela anterior e quem **gastou e não registrou resultado**),
  `relatorio <cliente>` (ontem contra a média da própria campanha) e
  `relatorio --mudas` (separa conta que **emudeceu** de conta que nunca teve
  linha — alertar na segunda treina você a ignorar o alerta).
- **`init`** — confere cofre, banco e schema, e **diz o que falta**. Setup que
  falha calado é como se descobre que o banco não tinha tabela depois do ETL
  rodar 20 contas.
- **`cliente` / `conta`** — a carteira, que mora no banco e não em arquivo
  versionado. `conta --remover` desativa sem apagar: o histórico continua
  valendo pra comparação do período anterior.
- **`imagem <cliente> <conta> <arquivo>`** — sobe a imagem e devolve o hash que
  a receita pede.

### Mudou

- **Um filtro de segredo só**, em `magicads/comum.py`. Antes `cli.py` e `etl.py`
  tinham cada um o seu — dois filtros não são redundância, são a chance de um
  ficar pra trás quando a regra mudar. Agora o token sai do cofre já registrado:
  quem chama não precisa lembrar de proteger.
- `magicads/banco.py` separado do ETL, com os dois backends (PostgREST e
  psycopg2) atrás de uma costura só, mais schema e carteira.
- `http()` ganhou `form=` — a Graph API quer POST urlencoded, Supabase e Google
  querem JSON. Misturar os dois dava erro que parecia de permissão.
- 55 testes (eram 16), todos stdlib. Os novos cobrem validação de receita e
  agregação do relatório.

## 0.1.0

Primeiro corte público: guia do app Meta, `diag` com os 6 portões, CLI de
leitura/escrita na Graph, ETL Meta + Google idempotente, schema de 4 tabelas e
os agentes Gandalf.
