# 3. O dia a dia

> Como isso se usa de verdade, na ordem em que as coisas acontecem.

## A regra que vale pra tudo: confira por `GET /<id>`

A Meta responde **HTTP 200 com lista vazia** quando está sob rate limit, quando o token não enxerga o ativo, e quando o campo pedido não se aplica. Nenhum desses casos é erro na resposta.

```bash
# ruim: se vier vazio, você não sabe se não existe ou se você não vê
python -m magicads get acme act_000000000000000/campaigns fields=name,status

# bom: leia o próprio id
python -m magicads get acme 120000000000000000 fields=name,status,effective_status
```

Vale para conferir subida, pausa, orçamento e qualquer coisa que você acabou de mudar.

## Antes de subir: `diag`

```bash
python -m magicads diag acme
```

Roda os 6 portões e termina com **PODE SUBIR** ou com a lista do que falta. Boa parte do que falta é ação do **cliente**, não sua:

| Portão | De quem é o conserto |
|---|---|
| token abre | do cliente (senha) ou seu (readicionar app + gerar token novo) |
| conta de anúncio aparece | seu (atribuir ao System User) |
| MANAGE/ADVERTISE | do cliente (papel na conta) |
| forma de pagamento | do cliente |
| Página | do cliente (compartilhar) |
| WhatsApp conectado na Página | **do cliente, e não tem atalho** |

Copie a lista e mande pra ele. É mais rápido do que descobrir isso no meio da subida.

## Subir

Subir na Graph são **quatro chamadas encadeadas** (campanha, conjunto, criativo,
anúncio), cada uma com campo obrigatório que a Meta só cobra depois, com
mensagem que não diz o que faltou. Montar isso na mão é como se perde a tarde.

Por isso o caminho é a **receita**: um JSON com o que muda, e o resto é trabalho
do código.

```bash
# 1. sobe o criativo e guarda o hash
python -m magicads imagem acme act_000000000000000 oferta.jpg

# 2. ENSAIO: imprime os quatro payloads e NAO chama a Meta
python -m magicads subir receitas/local-whatsapp.json

# 3. pra valer. Tudo nasce PAUSED, e nao existe flag pra subir ligado
python -m magicads subir receitas/local-whatsapp.json --executar
```

O ensaio é **offline de verdade**: ele nem lê o token do cofre. E a receita
recusa antes de sair da sua máquina o que a Meta recusaria depois: verba abaixo
do mínimo, falta de geografia, `promoted_object` ausente, criativo sem imagem,
vídeo sem capa.

Escolha a receita pelo **tipo de conta**, não pelo setor: `b2b-formulario`,
`local-whatsapp`, `loja-conversao`, `balcao-trafego`, `loja-video-reels`.

Se falhar no meio, ele imprime o que ficou de pé e o comando exato para remover,
do mais novo para o mais velho. Órfão silencioso é como se descobre, três
semanas depois, que existe campanha sua parada na conta de um cliente.

```bash
python -m magicads remover acme 120000000000000000 --executar
```

`remover` faz `DELETE` de verdade e **prova relendo o objeto por `GET`**. Não use
`post <id> _method=DELETE`: a Graph responde `{"success": true}` e não apaga
nada.

### ⚠️ O aviso que salva dinheiro

**`validate_only` não protege em `/campaigns`.** Nesse endpoint a Meta cria de
verdade, com ou sem a flag. Em **conjunto** e **anúncio** a flag funciona como
esperado.

Consequência prática: campanha é o único objeto onde o "ensaio" já é a peça. Por
isso o `post` **recusa** `/campaigns` sem `--executar`, em vez de avisar e mandar
assim mesmo, e por isso o `subir` ensaia **antes** de encostar na API.

### Campos que a Meta rejeita quando faltam

- `special_ad_categories`: obrigatório, mesmo vazio (`[]`)
- `is_adset_budget_sharing_enabled`: obrigatório quando a verba está no
  **conjunto** (ABO). Sem ele a campanha nem nasce, e a mensagem genérica diz só
  "Invalid parameter": o motivo real vive em `error_user_title`
- `promoted_object`: obrigatório em objetivo de conversão, mensagem e lead
- em CTWA, o número do WhatsApp mora dentro do `promoted_object`, não no criativo

## Suspender

```bash
python -m magicads pausar acme 120000000000000000
```

`pausar` **executa direto**, sem `--executar`. É de propósito: freio que exige confirmação é freio que não se usa na hora do aperto. Funciona em campanha, conjunto e anúncio, é só passar o id.

O caminho de volta é o contrário:

```bash
python -m magicads ativar acme 120000000000000000 --executar
```

`ativar` exige a flag porque religar volta a gastar.

Os dois conferem o resultado por `GET` logo depois e imprimem o `effective_status`. Atenção a essa diferença: `status=ACTIVE` com `effective_status=CAMPAIGN_PAUSED` significa que o anúncio está ligado dentro de uma campanha pausada, ou seja, não está rodando.

## Ler número

Para olhar uma coisa pontual, o `get` resolve:

```bash
python -m magicads get acme act_000000000000000/insights \
  fields=campaign_name,spend,impressions,clicks,actions \
  date_preset=last_7d level=campaign
```

Para **decidir**, não. Métrica lida no chat é métrica que você não compara com
ontem. Para decidir você quer a série no banco, e é o que os dois comandos
abaixo fazem:

```bash
# enche a serie. Idempotente: rodar dez vezes no mesmo dia nao duplica linha,
# porque a chave primaria E a chave de idempotencia.
python -m magicads etl --dias 7 --seco     # mostra e nao escreve
python -m magicads etl --dias 7

# le a serie em formato de DECISAO, nao de dashboard
python -m magicads relatorio               # portfolio, com delta vs a janela anterior
python -m magicads relatorio acme --dias 14
python -m magicads relatorio --mudas      # quem PAROU de reportar
```

`--mudas` sai em código 1 só quando alguma conta **emudeceu** (tinha linha e
parou), nunca quando nunca teve. Dá pra pendurar no cron e só receber e-mail
quando importa.

> `last_7d` **não inclui hoje**. Se o número não bate com o do gerenciador, é quase sempre isso ou fuso horário da conta.

## O loop de quem opera vários clientes

```
06:00  cron roda o ETL          → banco enche
 manhã  você abre o agente       → ele lê a série e diz onde tem sangramento
        magicads pausar ...      → freia o que estourou
        magicads subir receita.json  → sobe o substituto, PAUSED
        confere por GET /<id>    → e só então ativa
```

O agente entra no fim, não no começo. Enquanto não tem série no banco, ele opina sobre nada.
