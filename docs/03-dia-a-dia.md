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

`post` roda em **modo validação por padrão**: a Meta confere o payload e não cria nada.

```bash
# 1. valida
python -m magicads post acme act_000000000000000/campaigns \
  name="[C01] leads setembro" \
  objective=OUTCOME_LEADS \
  status=PAUSED \
  special_ad_categories="[]"

# 2. cria de verdade
python -m magicads post acme act_000000000000000/campaigns \
  name="[C01] leads setembro" objective=OUTCOME_LEADS status=PAUSED \
  special_ad_categories="[]" --executar
```

### ⚠️ O aviso que salva dinheiro

**`validate_only` não protege em `/campaigns`.** Nesse endpoint a Meta cria de verdade, com ou sem a flag. Em **conjunto** e **anúncio** a flag funciona como esperado.

Consequência prática: campanha é o único objeto onde o "ensaio" já é a peça. Por isso **suba sempre com `status=PAUSED`**, e por isso o CLI imprime o aviso quando o caminho termina em `/campaigns`.

### Campos que a Meta rejeita quando faltam

- `special_ad_categories`: obrigatório, mesmo vazio (`[]`)
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

Para **decidir**, não. Métrica lida no chat é métrica que você não compara com ontem. Para decidir você quer a série no banco (`db/schema.sql`), com o ETL rodando todo dia.

> `last_7d` **não inclui hoje**. Se o número não bate com o do gerenciador, é quase sempre isso ou fuso horário da conta.

## O loop de quem opera vários clientes

```
06:00  cron roda o ETL          → banco enche
 manhã  você abre o agente       → ele lê a série e diz onde tem sangramento
        magicads pausar ...      → freia o que estourou
        magicads post ... --executar → sobe o substituto, PAUSED
        confere por GET /<id>    → e só então ativa
```

O agente entra no fim, não no começo. Enquanto não tem série no banco, ele opina sobre nada.
