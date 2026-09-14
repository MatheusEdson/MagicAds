# Fluxo — medir, decidir, matar, escalar

Subir é a parte fácil. O dinheiro se ganha e se perde aqui.

> **Portão:** tudo neste fluxo é `LIVRE` até a decisão. Pausar é `FREIO`.
> Escalar (mexer em verba, religar) é `HUMANO`.

---

## 1. Encher a série antes de opinar

```bash
python -m magicads etl --dias 7
```

Idempotente: a chave primária **é** a chave de idempotência, então rodar duas
vezes no mesmo dia não duplica e não precisa de controle de "já rodei".

Sai com código 1 quando alguma conta falhou. **Falha não vira zero**: se a
chamada de uma conta quebrar, nada é escrito para ela — zero por erro de rede
vira "a campanha parou" no relatório, e aí alguém pausa o que estava indo bem.

---

## 2. As três leituras

```bash
python -m magicads relatorio                    # portfólio
python -m magicads relatorio <cliente> --dias 14  # por campanha
python -m magicads relatorio --mudas            # saúde da coleta
```

**Portfólio** dá investido, resultado, custo por resultado e o **Δ contra a
janela anterior de mesmo tamanho**. O Δ é o que transforma número em decisão:
"R$ 3.200 e 41 leads" não diz nada; "R$ 3.200, +120% e o mesmo número de leads"
diz tudo.

Ele também chama pelo nome quem **gastou e não registrou resultado nenhum**. Não
é detalhe de rodapé: ou o evento não está chegando, ou a verba está indo para o
lixo. Os dois pedem ação hoje, e nenhum dos dois aparece na média.

**Por campanha** compara ontem com a média diária da própria campanha. Campanha
que gastou ontem e não aparece na coluna de resultado é a primeira a olhar.

**`--mudas`** separa conta que **emudeceu** (tinha dado recente e parou) de conta
que nunca teve linha. Só a primeira é alarme, e sai com código 1 — dá para
pendurar no cron e só receber e-mail quando importa. Alertar na segunda todo dia
treina você a ignorar o alerta, e aí o alerta de verdade passa junto.

---

## 3. Decidir

Antes de qualquer conclusão, três perguntas que invalidam a leitura:

**A janela tem volume?** Abaixo de ~10 conversões no período, a diferença entre
duas campanhas é ruído. Decidir aí é sortear.

**O número está completo?** `last_7d` não inclui hoje. Conta em fuso diferente
fecha o dia em outra hora. Se o seu número não bate com o gerenciador, é quase
sempre um desses dois antes de ser bug.

**O resultado é resultado?** Conversa iniciada é o **denominador**, não o
resultado. Nenhuma delas é conversa qualificada, muito menos venda. Se a conta
só tem clique e nenhuma conversão registrada, o relatório mostra zero — e isso
é informação: ela não está medindo nada.

### O que matar

- campanha que gastou o equivalente a **3× o custo por resultado aceitável** sem
  um resultado
- criativo cujo custo por resultado é o dobro da média do conjunto, **com**
  volume suficiente para a comparação existir
- conjunto que a Meta não tira do aprendizado há duas semanas

### O que escalar

Escala é aumento de verba em **até ~20% por vez, com 48h entre um e outro**.
Dobrar verba reinicia o aprendizado, e aí você perdeu a campanha que estava
funcionando para descobrir se ela funcionava mais.

**Não divida verba para testar o que você não vai conseguir ler.** Três conjuntos
com R$ 20/dia cada não produzem três leituras, produzem três ruídos e um piso de
cobrança triplicado.

---

## 4. Executar a decisão

```bash
python -m magicads pausar <cliente> <id>                 # FREIO, direto
python -m magicads ativar <cliente> <id> --executar      # HUMANO
python -m magicads post   <cliente> <id> daily_budget=6000 --executar   # HUMANO
```

Depois de qualquer uma, confira por `GET` no próprio id. O `POST` responder 200
não prova que aplicou, e reler a lista prova menos ainda.

**Não mexa em targeting de campanha que está entregando bem.** A edição reenvia
os anúncios para revisão e reinicia o aprendizado. Se precisa mesmo mudar
público, crie conjunto novo ao lado e deixe o antigo morrer sozinho.

---

## 5. O ciclo automático

```bash
python -m magicads etl --dias 3          # de manhã
python -m magicads relatorio --mudas     # sai 1 quando alguém emudeceu
```

Pendure os dois no cron e faça o e-mail sair **só quando o código de saída for
1**. Relatório que chega todo dia vira relatório que ninguém abre.
