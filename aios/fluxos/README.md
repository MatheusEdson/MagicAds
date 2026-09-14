# Fluxos — o que fazer, em que ordem, por plataforma

O contrato (`python -m magicads contrato`) diz **quais ferramentas existem**.
Estes arquivos dizem **o ofício**: a sequência, o que conferir entre um passo e
outro, e onde parar e chamar gente.

A separação é de propósito. Ferramenta muda de versão em versão e por isso se
descreve sozinha. Ofício muda devagar e mora em texto.

---

## A matriz: o que cada plataforma deixa fazer

Esta tabela existe por um motivo só: **para o agente não prometer o que não tem
API.** Um agente que diz "vou publicar o produto no seu Google Meu Negócio" está
mentindo, e mentira de agente vira promessa para o cliente.

| Plataforma | Ler métrica | Subir campanha | Pausar/editar | Como |
|---|---|---|---|---|
| **Meta** (Facebook) | ✅ API | ✅ API | ✅ API | `magicads` ponta a ponta |
| **Instagram** | ✅ junto da Meta | ✅ junto da Meta | ✅ | **é posicionamento, não canal** |
| **Google Ads** | ✅ API (no ETL) | ⚠️ a API **dá**, aqui não tem | ⚠️ idem | subida é na interface, hoje |
| **Google Business** (GBP) | ⚠️ parcial | ❌ **não existe API** | ❌ | post e produto são na mão |
| **LinkedIn** | ❌ fora do ETL | ❌ | ❌ | API separada, ainda não integrada |

⚠️ **e** ❌ dizem coisas diferentes, e o agente precisa saber qual é qual.
❌ é “não existe”: no GBP ninguém sobe produto por API, nem você nem ferramenta
paga, então prometer é mentir. ⚠️ é “dá, mas não por aqui”: o Google Ads cria
campanha, grupo, anúncio e palavra-chave pela API sem problema — o que falta é
código deste repositório.

Pro agente isso muda a frase. Com ❌: “isso não tem API, tem que ser na mão”.
Com ⚠️: “dá pra automatizar, mas hoje eu não faço; te monto o plano e você
executa na interface”. **Nunca** “o Google não deixa”.

### Instagram não é um canal a mais

É a mesma Graph API, a mesma campanha, a mesma conta. O que muda é
`publisher_platforms` no targeting. Tratar como canal separado leva a criar
campanha duplicada e dividir verba entre duas coisas que a Meta já otimizava
junto — e [dividir verba mata a leitura](meta-operar.md).

O que **é** específico: sem `instagram_id` na receita, o anúncio roda no
Instagram com o nome e a foto da **Página do Facebook**. Funciona, entrega, e
parece de outra marca para quem vê.

### Google Business não tem API de produto

Não é limitação do MagicAds: a API do GBP não expõe produto. Post tem endpoint,
produto não. E termo novo na ficha demora da ordem de **dois meses** para
aparecer nas buscas, o que significa que a ficha é trabalho de mês, não de
sprint — e que medir mudança nela em sete dias não mede nada.

Tem mais um detalhe que engana: consulta ao GBP devolve `200` com lista vazia
quando não há o que devolver. Igual à Meta sob rate limit, e pela mesma razão
você não pode ler "vazio" como "não existe".

**O que o agente pode fazer aqui:** montar a lista do que mudar na ficha, na
ordem de impacto, e entregar para alguém executar. Isso é útil. Prometer que vai
executar, não.

### Google Ads: lê, não sobe

O ETL já traz custo, impressão, clique e conversão por campanha. Subir pela API
é possível e **não está implementado** — e isso é uma escolha, não um bug: a
subida no Google tem outra anatomia (palavra-chave, correspondência, negativa,
extensão) e portar o modelo de receita da Meta para lá sem isso produziria
campanha que roda e queima.

**O que o agente faz:** lê a série, aponta o que está caro, e monta o plano de
alteração. Você executa na interface.

---

## Como o agente usa isto

1. No começo da sessão, roda `python -m magicads contrato`. Passa a saber o que
   existe **nesta versão**, e não o que existia quando o texto foi escrito.
2. Identifica o tipo de conta (o porteiro `@gandalf` faz isso em 5 perguntas).
3. Abre o fluxo da tarefa e segue os passos, conferindo entre um e outro.
4. Respeita os portões do contrato: `LIVRE` roda, `ESCREVE` roda e conta,
   `FREIO` roda na emergência e avisa depois, `HUMANO` **nunca** roda — propõe o
   comando e espera.

## Os fluxos

| Fluxo | Quando |
|---|---|
| [`meta-subir.md`](meta-subir.md) | criar campanha: conversa, formulário ou venda |
| [`meta-operar.md`](meta-operar.md) | medir, decidir, matar, escalar |
| [`meta-emergencia.md`](meta-emergencia.md) | está gastando errado **agora** |
| [`instagram.md`](instagram.md) | posicionamento, identidade e o que muda no criativo |
| [`google-ads.md`](google-ads.md) | ler a série e montar o plano |
| [`gbp.md`](gbp.md) | a ficha, e por que ela não se automatiza |
| [`linkedin.md`](linkedin.md) | o que existe hoje, que é pouco |

## A regra que vale em todos

**Nenhum número sai sem ter vindo do banco ou de uma chamada feita nesta
sessão.** Métrica de memória é chute com cara de dado, e chute com cara de dado
é o que faz alguém pausar a campanha que estava funcionando.
