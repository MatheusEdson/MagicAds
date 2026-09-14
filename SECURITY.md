# Segurança

Este projeto mexe com token que cria anúncio e gasta dinheiro em conta de terceiro. As regras abaixo não são estilo: cada uma nasceu de um jeito conhecido de vazar.

## As regras que o código aplica sozinho

| Regra | Onde | Por quê |
|---|---|---|
| Token nunca é impresso | `limpa()`, **um só**, em `comum.py` | erro de API **ecoa o parâmetro que você mandou**. É assim que token vai parar no log, no print do terminal e no canal do time |
| Segredo só vem de variável de ambiente ou do cofre | `env()` em `comum.py` | arquivo de credencial no repo acaba commitado. Sempre |
| `post` valida antes de criar | `cmd_chamada` | `--executar` é explícito, e a ausência dele é o padrão |
| Falha não vira zero | `FALHAS` em `etl.py` | escrever zero por erro de rede vira "a campanha parou" no relatório |
| Carteira mora no banco | `Banco.carteira()` | arquivo de carteira é dado de cliente dentro do git, e ainda apodrece |
| Scrub antes do push | `scripts/scrub.sh` | verificação no olho não pega id real em comentário. A do repo já pegou um |

## O cofre

```bash
mkdir -p ~/.magicads/tokens
printf 'CLIENTE_META_TOKEN=EAA...\n' > ~/.magicads/tokens/cliente.env
chmod 600 ~/.magicads/tokens/cliente.env
```

1. **Um arquivo por cliente.** Vazar um não pode ser vazar a frota.
2. **`chmod 600`.** O CLI avisa quando não está — **no Windows ele avisa que NÃO checou**, porque bit de permissão POSIX não existe lá. Quem opera no Windows confere a ACL da pasta na mão (`icacls %USERPROFILE%\.magicads`).
3. **Nunca em pasta compartilhada.** `~/workspace`, Drive sincronizado, pasta de projeto: costumam ser legíveis pelo grupo, e sincronizam para lugares que você não controla.
4. **Nunca no repositório.** Uma vez no histórico do git, sai só reescrevendo história, e quem já clonou continua com a cópia.

Em servidor, prefira um gerenciador de segredo de verdade (Infisical, Doppler, 1Password, Secrets Manager) e injete como ambiente na hora de rodar.

## A chave do banco

O ETL escreve com a **service key**, que passa por fora de qualquer RLS. Isso é de propósito: leitor nunca escreve, escritor é só o ETL.

Consequência: essa chave **só existe no servidor**. Ela não vai para o front, não vai para o navegador, não vai para o repositório. Se precisar ler de algum lugar público, use a chave anônima com RLS ligada.

## Ligue o App Secret Proof

No painel do app Meta, Configurações Avançadas. Com ele ligado, as chamadas de servidor passam a exigir `appsecret_proof`, o que torna um token roubado inútil sem o app secret. É uma caixa de seleção e um HMAC.

## Antes de cada push

```bash
./scripts/scrub.sh       # a árvore de trabalho, antes de todo push
./scripts/historico.sh   # todo blob de todo commit, mais mensagens e autores
```

São duas perguntas diferentes. O `scrub` lê o que está na sua pasta agora.
Segredo que entrou num commit e **saiu no commit seguinte** some da árvore e
continua no pack — e o push leva o pack. Num repo público isso é definitivo:
vazou, e apagar depois não desfaz. O `historico.sh` é pra rodar uma vez antes
de abrir o repo, e de novo antes de mandar pra alguém.

As regras dos dois moram num arquivo só, `scripts/regras.sh`. Duas listas em
dois scripts garantem que uma hora uma regra entra numa e não na outra, e isso
não falha barulhento: falha calado, dizendo “limpo” sobre o que nunca olhou.

Os dois **recusam** em vez de assinar verde quando não têm como olhar: o scrub
planta iscas e exige encontrá-las; a varredura aborta em clone raso (`--depth 1`
e o checkout padrão do GitHub Actions trazem **um** commit) e aborta se a
própria isca dela não acender.

Nove checagens: token da Meta, chave longa, chave de serviço, chave privada, conta de anúncio, id longo, MCC, nome de cliente e telefone. Sai `1` quando acha algo.

Para não depender da sua memória, instale o hook:

```bash
cp scripts/hooks/pre-push .git/hooks/pre-push && chmod +x .git/hooks/pre-push
```

⚠️ **Crie o `.scrub-clientes.local`**, um nome por linha, com os clientes reais da sua carteira. Regex genérico não sabe que "Acme Pneus" é cliente seu, e é esse o vazamento que dói: não é o token, é o dado do cliente. O arquivo está no `.gitignore` de propósito: escrever os nomes dentro do `scrub.sh`, num repo público, seria vazar exatamente o que ele existe para proteger. Sem esse arquivo o scrub avisa, em vez de fingir que checou.

```bash
cp .scrub-clientes.local.exemplo .scrub-clientes.local
```

A busca casa **palavra inteira** e ignora maiúscula. Isso é de propósito: sem essa
regra, um nome de 5 letras da lista casou com uma palavra maior dentro do próprio
CHANGELOG e travou o push por causa de uma frase em português. Alarme falso é como
um scrub morre — primeiro irrita, depois ninguém lê a saída, e aí ele não protege
mais nada. A contrapartida é que "Acme" não pega "Acme-Store": liste as variações
que você usa.

Essa é a única regra que depende de um arquivo de fora, então é a única que pode
ficar calada sem ninguém notar. Por isso o autoteste planta uma isca com o
**primeiro nome da sua própria lista** e exige que o scrub a encontre.

## Se um token vazou

Nesta ordem:

1. **Revogue primeiro, investigue depois.** Business Settings → Usuários do sistema → o System User → remover o token. Revogar é reversível; o estrago não.
2. Gere um token novo e atualize o cofre.
3. Veja o que rodou com ele: Business Settings → Registro de Atividades do Negócio, filtrando pelo System User.
4. Se o vazamento foi para o git, **reescrever a história não basta**: quem clonou tem a cópia, e o GitHub guarda o objeto em cache por um tempo. O token precisa morrer de qualquer jeito.

## Reportando uma falha

Achou algo neste código que exponha token, permita escrita indevida ou vaze dado? Abra uma issue **sem o detalhe explorável** e me chame. Não publique reprodução funcional antes da correção.
