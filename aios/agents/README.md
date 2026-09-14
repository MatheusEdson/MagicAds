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

## O que eles têm em comum

Três regras aparecem nos quatro, e são as que evitam o estrago grande:

1. **Nenhum número sai sem ter vindo do banco ou de uma chamada feita na sessão.** Métrica de memória é chute com cara de dado.
2. **Antes de subir, `magicads diag <cliente>` tem que dar PODE SUBIR.** Metade do que ele acusa é ação do cliente, e descobrir isso antes economiza a tarde.
3. **Conta híbrida separa por campanha.** O evento de otimização é o volante; dois volantes no mesmo conjunto não dão meia direção, dão nenhuma.

## O que eles não fazem

Não gastam dinheiro sozinhos. O CLI executa, e `post` só cria com `--executar`. O agente propõe o comando, você lê e roda.
