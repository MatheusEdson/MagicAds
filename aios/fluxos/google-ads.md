# Fluxo — Google Ads

> **O que dá hoje: ler, subir Search, pausar e remover.**
> Não confunda com o Google Business, onde a API **não existe**. Aqui ela sempre
> existiu; o que você precisa ter é o nível de acesso do developer token (abaixo).

A subida demorou a existir, e não foi falta de API. A anatomia do Search é outra
— palavra-chave, tipo de correspondência, negativa, grupo de anúncio — e portar o
modelo de receita da Meta para lá sem essas peças produziria campanha que roda e
queima. Uma receita que gera Search sem lista de negativas é uma máquina de
comprar clique errado, em dois comandos.

A solução não foi documentar o risco, foi **recusar**: sem `grupo.negativas` e
sem `campanha.geo`, o código não monta o payload, e recusa antes de falar com o
Google.

---

## Ler

O ETL já traz Google junto da Meta, na mesma tabela e no mesmo formato:

```bash
python -m magicads etl --dias 7 --so-google
python -m magicads relatorio <cliente> --dias 14
```

No relatório o canal aparece na primeira coluna. **Campanha de mesmo nome em
canais diferentes não se mistura** — "[C01] Institucional" existe nos dois, e
somar esconde qual dos dois está caro.

### O que precisa estar no ambiente

```
MAGICADS_GADS_DEVELOPER_TOKEN
MAGICADS_GADS_LOGIN_CUSTOMER_ID      # o MCC, sem traços
MAGICADS_GOOGLE_CLIENT_ID
MAGICADS_GOOGLE_CLIENT_SECRET
MAGICADS_GADS_REFRESH_TOKEN
```

Sem o developer token o ETL **pula o canal e avisa**, em vez de falhar — para
quem só roda Meta não precisar configurar Google.

### Um erro que se disfarça de outro

A consulta usa intervalo **fechado** em `segments.date`. Um `>=` sozinho devolve
`EXPECTED_FILTERS_ON_DATE_RANGE`, que aparece como "invalid argument" e faz você
procurar erro de sintaxe onde não tem.

---

## Decidir

As mesmas três perguntas do [`meta-operar.md`](meta-operar.md) valem, mais duas
que são só do Google:

**De onde veio o clique?** Search, Display e Performance Max no mesmo relatório
sem separação misturam intenção com curiosidade. Display barato que não converte
puxa a média para baixo e parece eficiência.

**O ranking de produto sai do Shopping, não do pixel.** Se a pergunta é "qual
produto vende mais no pago", o lugar de olhar é o relatório de Shopping.

---

## Executar

```bash
python -m magicads subir receitas/google-search-local.json              # ensaio
python -m magicads subir receitas/google-search-local.json --conferir   # valida COM o Google
python -m magicads subir receitas/google-search-local.json --executar   # cria, PAUSED

python -m magicads pausar-google <conta> <id-da-campanha>               # freio
python -m magicads remover-google <conta> <id> --executar               # campanha E orçamento
```

### O que a receita recusa

| falta | por quê |
|---|---|
| `grupo.negativas` | Search sem negativa compra "grátis", "como fazer", "vaga de emprego", "curso" e o nome dos concorrentes. Lista vazia não conta |
| `campanha.geo` | sem geo a campanha entrega no **mundo inteiro**, e a métrica parece "só" ruim em vez de errada |
| menos de 3 títulos ou 2 descrições | o Google recusa, e a mensagem dele não diz qual campo |
| título > 30 ou descrição > 90 | idem, e o código conta antes de enviar |
| `conta` sem 10 dígitos | com ou sem traços, mas tem que ser o customer id |

### Três coisas que o código decide por você

**Display e Parceiros de Pesquisa desligados.** Os dois vêm **ligados** por
padrão na interface. É assim que Search vira Display sem ninguém ter decidido
isso, e aí o CPC despenca, o volume sobe, e a conversão some.

**Manual CPC.** Lance automático precisa de histórico de conversão pra ter o que
otimizar. Numa campanha que nasce hoje ele gasta pra aprender, e quem paga a aula
é o cliente. Troque depois que houver conversão entrando.

**Negativa em BROAD.** Negativa de frase deixa passar a variação, e a variação é
justamente o que você não quer comprar.

### `--conferir` só existe aqui, e o motivo importa

No Google Ads o `validateOnly` é honesto: valida a transação inteira e não cria
nada. Na Meta, `validate_only` em `/campaigns` **cria de verdade** — por isso o
`subir` da Meta ensaia offline e o `post` recusa campanha sem `--executar`.
Mesmo nome, comportamento oposto.

### Uma transação, não seis chamadas

Tudo sobe num `googleAds:mutate` só, com id temporário negativo amarrando
orçamento → campanha → grupo → anúncio. É atômico: ou entra tudo, ou não entra
nada. **Por isso aqui não existe órfão**, e não existe o "olha o que já foi
criado" que o `subir` da Meta precisa ter.

A primeira versão chamava um serviço por vez, e tinha os dois defeitos: o
`--conferir` nunca passava (sem criação não há `resourceName` pra referenciar, e
a campanha era recusada por `campaign_budget REQUIRED`), e falha no meio deixava
orçamento órfão na conta do cliente.

### O orçamento não vai junto com a campanha

Remover a campanha deixa o `campaignBudget` vivo e sem dono, e ele não aparece em
nenhuma tela que você olha no dia a dia. Como este módulo cria um orçamento por
campanha, ele seria o próprio produtor do lixo. Por isso `remover-google` apaga
os dois, e **prova relendo**.

Prova por leitura, nunca pela resposta do mutate. A lição veio da Meta, onde o
`_method=DELETE` devolve sucesso com o objeto vivo: resposta de sucesso não é
prova de nada.

### Um campo que aparece do nada e quebra tudo

`contains_eu_political_advertising` virou **obrigatório** em toda campanha (regra
de publicidade política da UE). Sem ele o Google devolve `REQUIRED` com a
mensagem genérica "The required field was not present.", e o nome do campo só
aparece dentro de `location.fieldPathElements` — que é exatamente o pedaço que
some quando você trunca o erro pra caber na tela. Por isso o módulo **traduz** o
erro do Google em vez de imprimir os primeiros 400 caracteres dele.

### O portão pra usar isso não é técnico

É burocrático, e leva **dias**, não minutos:

1. O `developer token` sai no **API Center de uma conta de administrador (MCC)**.
   Conta comum não emite.
2. Ele nasce em **acesso de teste**, que só fala com **contas de teste**. É a
   pegadinha: o token parece válido, autentica, e só quebra quando você aponta
   pra conta de verdade.
3. Pra tocar conta de produção você **solicita** a subida de nível (acesso
   básico) num formulário, e o Google revisa. Depois existe ainda o nível padrão,
   que solta o limite de operações por dia.

Quem já lê produção no ETL daqui **já passou** por esse portão: acesso de teste
não leria conta de cliente. Pra quem começa do zero, o pedido é o primeiro passo
e não dá pra pular.

### O que continua sendo na interface

Extensões (sitelink, chamada, local), Performance Max, Shopping, e edição de
texto de anúncio existente. Criativo do Google, como o da Meta, não se edita:
troca-se por um novo.

E o passo que nenhuma API faz por você: **no dia 7, abrir o relatório de termos
de pesquisa** (não o de palavras-chave, são coisas diferentes) e engordar a lista
de negativas com o que apareceu e não devia.
