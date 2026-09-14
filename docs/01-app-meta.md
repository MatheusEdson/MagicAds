# 1. O app Meta: o caminho que não cai em App Review

> Este é o passo que trava quase todo mundo, e quase sempre por uma escolha feita na
> segunda tela. Leia até o fim antes de clicar.

## O que você está criando

Um **app Business** no seu portfólio, no [developers.facebook.com](https://developers.facebook.com). Ele é o intermediário entre o seu código e as contas de anúncio. O modelo inteiro é:

```
1 portfólio  →  1 app  →  1 System User  →  1 token  →  N contas de anúncio
```

Você cria o app **uma vez**. Cada cliente novo depois disso é só atribuir a conta dele ao mesmo System User.

## A escolha que decide tudo: o caso de uso

Na tela **"Adicionar casos de uso"**, a tentação é marcar os três de "Anúncios e monetização". Não marque.

Ao marcar os três, o fluxo empacota **nove casos de uso**, e a tela de visão geral passa a dizer:

> *"Verificação da Empresa e Análise do App exigidos para 8 casos de uso"*

Oito de nove. E aí você trava numa fila de aprovação antes de ter escrito uma linha de código.

| Caso de uso | Marcar | O que exige |
|---|---|---|
| **Criar e gerenciar anúncios com a API de Marketing** | ✅ **só este** | nada. Standard Access é auto-aprovado |
| Mensurar dados de desempenho com a API de Marketing | ❌ por ora | Verificação da Empresa |
| Capturar e gerenciar leads com a API de Marketing | ❌ por ora | Verificação da Empresa |
| Anúncios de apps, Threads, Vídeo ao Vivo, oEmbed, Página, ThreatExchange, WhatsApp, jogos | ❌ | fora do escopo |

**O detalhe que faz esse caminho funcionar:** "Criar e gerenciar anúncios" habilita `ads_management`, e `ads_management` **já inclui leitura de insights**. Ou seja, com o caso de uso que não exige verificação você consegue:

- criar campanha, conjunto e anúncio
- ler `/insights` (o que alimenta relatório e monitoramento)
- ler criativo, público, pixel

Marcar "Mensurar desempenho" te dá `ads_read`, que é um **subconjunto** do que você já tem. Você entraria numa fila de verificação para ganhar menos do que já possui.

## Standard Access contra Advanced Access

Esta é a parte que a documentação explica mal e que faz todo mundo achar que precisa de App Review.

| | Standard Access | Advanced Access |
|---|---|---|
| Como se consegue | **auto-aprovado**, já vem | Verificação da Empresa + App Review por permissão |
| Para que serve | acessar dados de quem **tem papel no app** ou de ativos atribuídos ao seu System User | acessar dados de gente que **não tem relação nenhuma** com o app |
| Quem precisa | operação própria, agência, consultor | SaaS público com "entrar com Facebook" de estranhos |

Se você opera contas que administra, atribuídas ao seu System User, **você está em Standard Access e não precisa de review**. A referência de `ads_management` fala em agir "em nome de outros negócios", o que assusta, mas o que resolve a zona cinza é concreto: **atribua a conta do cliente ao seu System User** (o passo do `docs/02-token.md`).

## O gate que existe e não é review

**Marketing API Access Tier.** App novo nasce com limite de chamadas baixo. O upgrade é **automático** ao bater 500 chamadas em 15 dias. Isso afeta volume, não permissão, e não tem formulário.

Na prática: nos primeiros dias você pode bater rate limit lendo muita conta de uma vez. Não é bloqueio, é ritmo.

## Versão da API

Fixe a versão nas suas chamadas. A Meta versiona a cada poucos meses e o comportamento muda entre versões.

```bash
export MAGICADS_API_VERSION=v25.0   # o CLI usa esta, e é o default
```

## Quando você vai bater na parede

Dois recursos **exigem Verificação da Empresa**, e não tem caminho lateral no app:

1. **`leads_retrieval`**, que é como você puxa lead de formulário instantâneo
2. **Tiers mais altos** de acesso

A Verificação da Empresa pede documento de empresa: CNPJ, contrato social, comprovante de endereço comercial, conta em nome do negócio. É aqui que quem não tem empresa aberta para.

**Isso não bloqueia o MVP.** Criar, gerenciar, ler insights, ler criativo, montar relatório e monitorar, tudo isso roda sem verificação nenhuma. Formulário instantâneo fica para depois.

👉 Sobre o que fazer quando você **não tem CNPJ**: [`docs/04-quando-trava.md`](04-quando-trava.md).

## Checklist antes de ir para o token

- [ ] app criado no **seu** portfólio (não no do cliente)
- [ ] **só** "Criar e gerenciar anúncios com a API de Marketing" marcado
- [ ] a tela de visão geral **não** está pedindo Verificação da Empresa
- [ ] você anotou o App ID e o App Secret (Configurações → Básico)
- [ ] versão da API decidida e fixada

Próximo: [`docs/02-token.md`](02-token.md).
