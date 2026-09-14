# Fluxo — Google Ads

> **O que dá hoje: ler.** Subir pela API é possível e **não está implementado**.

Isso é escolha, não bug. A subida no Google tem outra anatomia — palavra-chave,
tipo de correspondência, negativa, extensão, grupo de anúncio — e portar o modelo
de receita da Meta para lá sem essas peças produziria campanha que roda e queima.
Uma receita que gera Search sem lista de negativas é uma máquina de comprar
clique errado.

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

Na interface, hoje. O agente monta o plano — o que pausar, qual verba, quais
negativas — e você executa lá.

Isso não é fraqueza do fluxo: é o agente sendo honesto sobre onde a mão dele
chega. O plano escrito com a série na frente já é a maior parte do trabalho.
