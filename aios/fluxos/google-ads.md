# Fluxo — Google Ads

> **O que dá hoje: ler.** Subir pela API é possível e **não está implementado**.
> Não confunda com o Google Business, onde a API **não existe**. Aqui ela existe;
> falta código, e falta você ter **solicitado** o nível de acesso do token (abaixo).

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

**Mas não diga que o Google não deixa.** Deixa. `CampaignService`,
`AdGroupService`, `AdGroupAdService` e `AdGroupCriterionService` criam campanha,
grupo, anúncio e palavra-chave por API. Quem não faz é este repositório.

### O portão pra implementar não é técnico

É burocrático, e leva **dias**, não minutos:

1. O `developer token` sai no **API Center de uma conta de administrador (MCC)**.
   Conta comum não emite.
2. Ele nasce em **acesso de teste**, que só fala com **contas de teste**. É a
   pegadinha: o token parece válido, autentica, e devolve erro quando você
   aponta pra conta de verdade.
3. Pra tocar conta de produção você **solicita** a subida de nível (acesso
   básico) num formulário, e o Google revisa. Depois existe ainda o nível
   padrão, que solta o limite de operações por dia.

Quem já lê produção no ETL daqui **já passou** por esse portão: acesso de teste
não leria conta de cliente. Então pra essa pessoa falta só o código. Pra quem
começa do zero, o pedido é o primeiro passo e não dá pra pular.

E a ressalva do topo continua de pé: o que trava a implementação **aqui** não é
o acesso, é o modelo de receita. Search sem lista de negativas é uma máquina de
comprar clique errado, e uma receita que gera isso em dois comandos é pior que
não ter receita nenhuma.
