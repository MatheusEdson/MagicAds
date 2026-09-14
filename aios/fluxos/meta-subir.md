# Fluxo — subir campanha na Meta

Vale para os três destinos. Onde muda, está marcado.

> **Portão:** o ensaio é `LIVRE` (não sai da máquina). O `--executar` é `HUMANO`:
> o agente monta, mostra e espera. Não cola o `--executar` sozinho.

---

## 0. Antes de tudo: o diag tem que dar PODE SUBIR

```bash
python -m magicads diag <cliente>
```

Seis portões, e **cinco deles não aparecem antes de você tentar subir**: token,
conta, permissão de escrita, forma de pagamento, Página e WhatsApp conectado.

Metade do que ele acusa é **ação do cliente**, não sua. Quando faltar algo dele,
pare o fluxo e mande a lista pronta — insistir daqui não resolve, e você vai
gastar a tarde descobrindo isso sozinho.

O portão do WhatsApp merece frase própria: a Página pode ter a tarefa de
mensagem e **não** ter número conectado. Nenhuma leitura da API mostra isso. O
`diag` descobre mandando um conjunto de teste em `validate_only`, que a Meta
confere e não cria — e o erro que denuncia é o `subcode 2446886`. O conserto é
do cliente, no Business Suite da Página, em Contas Vinculadas. Não existe atalho
pelo seu lado.

---

## 1. A mídia primeiro

O criativo precisa estar na biblioteca da conta **antes** da receita existir.

```bash
python -m magicads imagem <cliente> <act_...> criativo.jpg   # devolve imagem_hash
python -m magicads video  <cliente> <act_...> criativo.mp4   # devolve video_id
```

Vídeo também exige uma **capa**: escolha um frame, suba com `imagem` e ponha o
hash em `capa_hash`. Sem capa a Meta sorteia um frame, e frame sorteado de vídeo
vertical costuma ser a pessoa de olho fechado.

O `video_id` que sai daqui é o que serve para montar público de visualização
depois. O arquivo no seu disco não existe para a Meta.

---

## 2. A receita

Copie a do tipo de conta e troque o que muda:

| Tipo | Receita | Destino |
|---|---|---|
| B2B, alto ticket | `receitas/b2b-formulario.json` | formulário instantâneo |
| Serviço local | `receitas/local-whatsapp.json` | conversa no WhatsApp |
| Loja, e-commerce | `receitas/loja-conversao.json` | site + pixel |
| Balcão, delivery | `receitas/balcao-trafego.json` | site |

Três campos decidem mais do que todo o resto:

**`verba_diaria` é em CENTAVOS.** Escrever `50` achando "R$ 50" é o erro mais
comum, e a receita para nele antes de sair da máquina.

**`evento` (loja) é o volante.** Ele manda mais na entrega do que o público.
Otimizar por `ADD_TO_CART` enche o relatório e não enche o caixa. Só desça do
`PURCHASE` se a conta não tiver volume — abaixo de ~10 conversões por semana a
Meta não sai do aprendizado, e aí o número que você lê não significa nada.

**`advantage_audience`.** Em `1`, a demografia que você travou vira decorativa: a
Meta entrega fora da faixa. Em público grande isso costuma baratear; em público
pequeno e específico (B2B), costuma doer.

---

## 3. Ensaio — e ler o ensaio

```bash
python -m magicads subir receitas/<a-sua>.json
```

Imprime os quatro payloads e **não chama a Meta**. Não é formalidade: é onde
você vê o `targeting` montado, o `promoted_object` e o botão.

Confira três coisas no que saiu:

- a geografia é a que você combinou, e não a que estava no exemplo
- o `promoted_object` existe e aponta para o certo (Página, pixel, formulário)
- o `daily_budget` tem duas casas a mais do que você esperava, porque é centavo

Os **avisos** não barram. Barrar escolha legítima só ensina a pessoa a
contornar o próprio aviso.

---

## 4. Executar

```bash
python -m magicads subir receitas/<a-sua>.json --executar
```

**Tudo nasce PAUSED, e não existe flag para subir ligado.**

A ordem é campanha → conjunto → criativo → anúncio. O conjunto passa por
`validate_only` antes de valer; a campanha não passa, porque **`validate_only`
não protege em `/campaigns`** — nesse endpoint a Meta cria de verdade com ou sem
a flag. Por isso a campanha nasce pausada e por isso não existe "ensaio de
verdade" para ela.

Se falhar no meio, o comando imprime o que já ficou de pé e o comando exato para
remover. Órfão silencioso é como se descobre, três semanas depois, que tem
campanha sua parada na conta de um cliente.

---

## 5. Conferir — por `GET`, nunca por listagem

O `subir` já confere sozinho. Quando conferir na mão:

```bash
python -m magicads get <cliente> <id> fields=id,name,status,effective_status
```

**Nunca pela lista.** Sob rate limit a Meta devolve `data:[]` com HTTP 200, e
isso não é "não tem", é "não vejo". Metade dos bugs de integração é isso.

---

## 6. Ligar

```bash
python -m magicads ativar <cliente> <id> --executar
```

`HUMANO`. Revise no gerenciador antes: é o último momento em que o erro ainda é
barato.

---

## Depois de ligar

- **Não mexa no targeting por 72h.** Editar targeting **reenvia os anúncios para
  revisão** e reinicia o aprendizado. Você troca um problema por dois.
- `last_7d` **não inclui hoje**. Quando o número não bate com o gerenciador, é
  quase sempre isso ou fuso da conta.
- Se ligou vários conjuntos com CBO e verba pequena: o **mínimo é cobrado por
  conjunto ativo**, então o piso pode estourar o que você planejou.
