# 4. Quando trava: a Verificação da Empresa

> Aqui é onde a maioria desiste e vai alugar um SaaS por mensalidade. Vale entender
> exatamente o que está travado, porque geralmente é menos do que parece.

## O que está travado, e o que não está

Sem Verificação da Empresa você **ainda** faz:

- criar campanha, conjunto e anúncio
- ler `/insights` (relatório, monitoramento, série histórica)
- ler criativo, público, pixel, conta, página
- pausar, ativar, editar orçamento
- operar quantas contas de cliente quiser, desde que atribuídas ao seu System User

Ou seja: **a operação inteira deste repo roda sem verificação.**

O que fica bloqueado:

| Bloqueado | Impacto real |
|---|---|
| `leads_retrieval` | você não puxa lead de **formulário instantâneo** pela API. Ainda dá pra baixar CSV na mão, ou usar destino que não seja formulário (site, WhatsApp) |
| Tiers mais altos de acesso | teto de chamadas menor. Incomoda em frota grande, não em começo |
| Alguns casos de uso que você não marcou | fora do escopo daqui |

Se o seu funil é **WhatsApp ou site**, você pode nunca precisar verificar.
Se o seu funil é **formulário instantâneo**, precisa.

## O que a Meta pede

Documento que prove que o negócio existe e que o endereço é dele:

- CNPJ, contrato social ou certificado de MEI
- comprovante de endereço **em nome do negócio** (conta de luz, água, internet)
- extrato bancário empresarial
- contrato de locação comercial

⚠️ **Conta de consumo pessoal ou extrato pessoal em nome de uma empresa registrada é recusado.** O documento tem que ter o negócio como titular. Isso derruba muita submissão de primeira viagem.

E o nome do negócio no formulário tem que bater **exatamente** com o que está no documento. Abreviação diferente já reprova.

## Não tem empresa aberta

Existem caminhos, e eles não são segredo nenhum:

1. **"Ainda não registrado"**: o fluxo da Meta prevê negócio sem registro formal, e aí a prova vira operação (contrato, conta de consumo, extrato) em vez de documento societário.
2. **Sinal técnico, que ganhou peso em 2026**: propriedade de domínio verificada por registro DNS TXT, e-mail profissional no mesmo domínio, e identificação biométrica pessoal. Em alguns fluxos isso substitui parte do papel.
3. **MEI**: abrir custa pouco e resolve de vez, desde que o CNAE cubra a atividade que você anuncia.

**O que este repo não traz:** o passo a passo exato da submissão que passa de primeira, com a ordem das telas, o que escrever em cada campo e o que fazer depois de uma recusa. Isso é conhecimento de tentativa e erro, e vai embora no dia em que virar post viral: caminho de verificação muito divulgado é caminho que a plataforma aperta.

Se você chegou nesse ponto e travou, fale comigo.

## Antes de submeter, confira

- [ ] nome do negócio **idêntico** ao do documento
- [ ] documento com o **negócio** como titular, não você
- [ ] endereço do documento igual ao do formulário
- [ ] domínio verificado (DNS TXT) se você tiver um
- [ ] e-mail do mesmo domínio, não Gmail
- [ ] uma submissão de cada vez: recusa em série deixa rastro
