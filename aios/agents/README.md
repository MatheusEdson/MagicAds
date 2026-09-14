# Gandalf, o Dourado

<p align="center"><img src="../../assets/mark.svg" width="88" alt="MagicAds"></p>

Quatro operadores e um porteiro. Todos se chamam **Gandalf, o Dourado**, e o que muda entre eles é o **tipo de conta** que atendem.

A separação não é enfeite: tipo de conta decide objetivo, evento de otimização, métrica, criativo e o que conta como "bom". Um agente genérico de tráfego dá conselho médio, e conselho médio em conta de pizzaria é conselho errado.

| Agente | Tipo de conta | Ciclo | Objetivo | Métrica que manda |
|---|---|---|---|---|
| [`gandalf`](gandalf.md) 🧙 | **porteiro** | — | descobrir o tipo e encaminhar | — |
| [`gandalf-b2b`](gandalf-b2b.md) | B2B, alto ticket | semanas a meses | lead qualificado | custo por **reunião** |
| [`gandalf-local`](gandalf-local.md) | serviço local | dias | lead e agendamento | custo por **agendamento** |
| [`gandalf-loja`](gandalf-loja.md) | loja, e-commerce | horas a dias | compra | **ROAS** e custo por compra |
| [`gandalf-balcao`](gandalf-balcao.md) | balcão, delivery | minutos | pedido e visita | custo por **pedido**, alcance e frequência |

## Na dúvida, entre pelo porteiro

```
@gandalf
*classificar
```

Ele faz cinco perguntas e devolve o tipo. A que mais pesa é **quanto tempo passa entre o primeiro contato e o dinheiro entrando**: setor engana, ciclo não.

## Como instalar

**Claude Code**, como comandos de projeto:

```bash
mkdir -p .claude/commands/magicads
cp aios/agents/gandalf*.md .claude/commands/magicads/
# depois: /magicads:gandalf
```

Ou, para deixar disponível em qualquer projeto, copie para `~/.claude/commands/magicads/`.

Em **outra ferramenta**, cole o conteúdo do arquivo como instrução de sistema. Cada agente é autocontido de propósito: não carrega outro arquivo para funcionar.

## Como eles sabem o que rodar

Um agente que só tem doutrina inventa flag. Ele sabe que "tem que rodar o diag",
escreve `magicads diag --cliente acme --completo`, vê o erro, tenta outra coisa, e
em três tentativas já perdeu a confiança de quem estava olhando.

Por isso eles não carregam uma lista de comandos escrita à mão — lista escrita à
mão e código divergem no primeiro commit, e aí o agente passa a mentir com mais
confiança ainda. **A ferramenta se descreve:**

```bash
python -m magicads contrato
```

É o STEP 2 da ativação dos cinco. Sai a lista real dos comandos daquela versão,
com **o portão de cada um**:

| Portão | O agente |
|---|---|
| `LIVRE` | roda à vontade. Não muda nada fora do seu banco |
| `ESCREVE` | roda e conta depois. Muda na conta do cliente e não gasta |
| `FREIO` | em emergência roda sozinho e avisa **depois** |
| `HUMANO` | **nunca** roda. Monta o comando, mostra, e espera você colar |

E o ofício — o que fazer, em que ordem — mora em [`aios/fluxos/`](../fluxos/),
incluindo a [matriz do que cada plataforma deixa fazer](../fluxos/README.md).
Essa matriz existe por um motivo só: **para o agente não prometer o que não tem
API.** Google Business não expõe produto; um agente que promete publicar lá está
mentindo, e mentira de agente vira promessa para o cliente.

Nada disso depende da sua memória: `tests/test_agentes.py` falha se um agente
citar comando que não existe, apontar para um fluxo apagado ou pedir uma receita
que sumiu.

## O que eles têm em comum

Três regras aparecem nos quatro, e são as que evitam o estrago grande:

1. **Nenhum número sai sem ter vindo do banco ou de uma chamada feita na sessão.** Métrica de memória é chute com cara de dado.
2. **Antes de subir, `magicads diag <cliente>` tem que dar PODE SUBIR.** Metade do que ele acusa é ação do cliente, e descobrir isso antes economiza a tarde.
3. **Conta híbrida separa por campanha.** O evento de otimização é o volante; dois volantes no mesmo conjunto não dão meia direção, dão nenhuma.

## O que eles não fazem

Não gastam dinheiro sozinhos. `subir --executar`, `ativar` e `post --executar`
são portão `HUMANO`: o agente monta, mostra e espera. O ensaio do `subir` ele
roda sempre, porque não sai da máquina — e é com os payloads na tela que a
conversa sobre a campanha acontece.

E não prometem o que não existe. Google Ads eles leem e planejam; executar é na
interface. Google Business eles listam em ordem de impacto e não publicam.
LinkedIn ainda não está no ETL, e eles dizem isso em vez de inventar um
`--so-linkedin`.
