# Fluxo — LinkedIn

> **Hoje: nada integrado.** API separada, fora do ETL. Isto existe para o agente
> não inventar comando, e para você saber o que esperar.

---

## Por que ainda não entrou

Não é a mesma Graph. É outra API, outro OAuth, outro modelo de objeto. Somar
LinkedIn não é "somar canal": é escrever um coletor novo.

E tem um detalhe que atrasa qualquer diagnóstico: o endpoint de **introspecção de
token do LinkedIn diz `revoked` com token vivo**. Ou seja, a ferramenta que
existe justamente para responder "meu acesso está bom?" responde errado. Quem
confia nela passa a tarde regenerando credencial que já funcionava.

**Como se prova acesso no LinkedIn:** fazendo uma chamada de leitura de verdade e
vendo se ela volta. Não pelo introspect.

---

## Quando ele é o canal certo

Em **B2B de ticket alto**, e quase só aí. A segmentação por cargo, empresa e
setor não tem equivalente na Meta, e é por ela que se paga o clique muito mais
caro.

Se o ciclo do cliente é de dias e o ticket é baixo, LinkedIn é caro sem ser
melhor — e o `@gandalf-b2b` deve dizer isso em vez de empurrar o canal.

---

## O que dá para fazer hoje

O agente trabalha o LinkedIn **fora da ferramenta**: plano de campanha,
segmentação, copy, e a leitura dos números que você trouxer. O que ele não faz é
fingir que existe `magicads etl --so-linkedin`.

Quando entrar, entra no mesmo formato: uma linha por dia por campanha na tabela
`metricas`, com `canal = linkedin`. O schema já comporta — é o coletor que falta.
