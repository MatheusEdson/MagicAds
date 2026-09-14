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
| **Google Ads** | ✅ API (no ETL) | ✅ Search, por receita | ✅ `pausar-google`, `remover-google` | negativas são **obrigatórias** na receita |
| **Google Business** (GBP) | ⚠️ parcial | ❌ **não existe API** | ❌ | post e produto são na mão |
| **LinkedIn** | ❌ fora do ETL | ❌ | ❌ | API separada, ainda não integrada |

❌ aqui é **“não existe”**, não “não fizemos”. No GBP ninguém sobe produto por
API, nem você nem ferramenta paga, então prometer é mentir. O Google Ads era
“dá, mas não por aqui”, e virou ✅: Search sobe por receita, numa transação
atômica, nascendo PAUSED.

**A regra do Search que o agente precisa repetir:** a lista de negativas é
obrigatória, e a recusa acontece antes de falar com o Google. Search sem
negativa compra “grátis”, “como fazer”, “vaga de emprego”, “curso” e o nome dos
concorrentes. O mesmo vale pro `geo`: sem ele a campanha entrega no mundo
inteiro, e isso queima verba mais silenciosamente ainda, porque a métrica
parece “só” ruim em vez de errada.

O que o agente **não** pode dizer sobre o GBP: “vou publicar o produto”. O que
ele **não** pode mais dizer sobre o Google Ads: “o Google não deixa”, nem
“executar é na interface”.

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

### Google Ads: lê e sobe Search, com a negativa como preço de entrada

O ETL traz custo, impressão, clique e conversão por campanha, e a subida de
Search existe desde a 1.8.0. Ela demorou de propósito: a anatomia do Search é
outra (palavra-chave, correspondência, negativa, grupo de anúncio), e portar o
modelo de receita da Meta para lá sem essas peças produziria campanha que roda e
queima. A saída não foi documentar o risco, foi **recusar** a receita.

Tudo sobe numa transação atômica (orçamento, campanha, grupo, palavras,
negativas e anúncio de uma vez), nasce `PAUSED`, e com Display e Parceiros de
Pesquisa **desligados** — os dois vêm ligados por padrão na interface, e é assim
que Search vira Display sem ninguém ter decidido isso.

**O que o agente faz:** lê a série, aponta o que está caro, monta a receita,
roda o ensaio, e o `--executar` é seu. Depois, `pausar-google` é freio e
`remover-google` apaga campanha **e orçamento** (o orçamento não vai junto: fica
vivo e sem dono).

**O que continua na interface:** extensão, Performance Max, Shopping, edição de
texto de anúncio — e o passo do dia 7, que é abrir o relatório de **termos de
pesquisa** e engordar a lista de negativas. Detalhe em
[`google-ads.md`](google-ads.md).

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
| [`google-ads.md`](google-ads.md) | ler a série, subir Search, pausar e remover |
| [`gbp.md`](gbp.md) | a ficha, e por que ela não se automatiza |
| [`linkedin.md`](linkedin.md) | o que existe hoje, que é pouco |

## A regra que vale em todos

**Nenhum número sai sem ter vindo do banco ou de uma chamada feita nesta
sessão.** Métrica de memória é chute com cara de dado, e chute com cara de dado
é o que faz alguém pausar a campanha que estava funcionando.
