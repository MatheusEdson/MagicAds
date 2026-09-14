# Changelog

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
