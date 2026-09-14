# Fluxo — está gastando errado agora

Este é o único fluxo em que o agente age antes de perguntar.

> **Portão:** `FREIO`. Pausar é a direção segura: não gasta, não apaga, não
> perde histórico. Em emergência o agente roda e **avisa depois**. Pedir
> autorização antes é exatamente o que faz a conta gastar mais uma hora enquanto
> alguém lê a mensagem.

---

## 1. Pisar no freio

```bash
python -m magicads pausar <cliente> --tudo
```

Pausa toda campanha ativa das contas daquele cliente. Executa direto — digitar
`--tudo` já é a confirmação.

A lista de contas sai da **carteira**, nunca de `me/adaccounts`. O token quase
sempre enxerga conta de cliente vizinho, e pausar a campanha do vizinho às 23h é
pior do que o problema que você estava resolvendo. Sem carteira, o comando exige
o `act_` na mão e se recusa a adivinhar.

Se a carteira não estiver cadastrada:

```bash
python -m magicads pausar <cliente> --tudo act_...
```

## 2. Ler a saída com desconfiança

Duas linhas importam mais que o resto:

**"sem campanha ativa"** não é "tudo certo". `data:[]` com HTTP 200 é também o
que a Meta devolve sob rate limit — e subida em massa é justamente o que derruba
a conta no rate limit. Se você **sabe** que tinha campanha rodando, espere um
minuto e rode de novo antes de acreditar.

**"AINDA ATIVAS depois do POST"** significa que a Meta aceitou e não aplicou.
Acontece. Rode de novo.

O comando sai com código 1 quando algo falhou ou continuou ativo. Em script,
trate 0 como "parou mesmo".

---

## 3. Só então descobrir o que foi

```bash
python -m magicads relatorio <cliente> --dias 3
python -m magicads get <cliente> <act_...>/campaigns fields=name,status,daily_budget,effective_status
```

As causas que aparecem quase sempre:

- **verba em centavos errada** — `daily_budget=50000` é R$ 500/dia, não R$ 50
- **CBO com vários conjuntos ligados** — o mínimo é cobrado **por conjunto
  ativo**, e o piso estoura o planejado sem ninguém ter mexido em nada
- **público muito aberto com `advantage_audience:1`** — entrega fora da faixa e
  o custo por resultado sobe enquanto o volume parece ótimo
- **campanha duplicada** — subiu duas vezes porque o primeiro `--executar`
  pareceu ter falhado quando na verdade era leitura vazia por rate limit

## 4. Religar, uma a uma

```bash
python -m magicads ativar <cliente> <id> --executar
```

`HUMANO`, e **não existe `ativar --tudo`**. Religar a conta inteira de uma vez é
como você descobre no extrato o que devia ter revisado antes.
