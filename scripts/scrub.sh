#!/usr/bin/env bash
# Scrub: nada de segredo nem de dado de cliente entra neste repo.
#
# Rode ANTES de todo push. Sai 0 quando esta limpo, 1 quando achou algo.
#   ./scripts/scrub.sh
#
# Se voce forkou isto pra sua operacao, edite CLIENTES abaixo com os nomes
# reais da SUA carteira. E o unico jeito de o scrub te proteger de verdade:
# regex generico nao sabe que "Acme Pneus" e cliente seu.
#
# `git grep --untracked` nao e detalhe: SEM essa flag o scrub le so o que ja
# esta rastreado, ou seja, aprova exatamente o arquivo NOVO que voce esta
# prestes a adicionar -- que e o caso mais provavel de vazamento. Ele continua
# respeitando o .gitignore, entao o cofre e os .env de verdade seguem de fora.

set -uo pipefail
cd "$(dirname "$0")/.."

falhou=0

achou() {   # <titulo> <regex>
    local titulo="$1" regex="$2"
    local hits
    hits=$(git grep --untracked -nIiE "$regex" -- . ':!scripts/scrub.sh' 2>/dev/null \
           | grep -vE 'x{8,}|0{8,}|000000000000000|EXEMPLO|exemplo|placeholder' || true)
    if [ -n "$hits" ]; then
        echo "FALHOU: $titulo"
        echo "$hits" | sed 's/^/    /'
        falhou=1
    else
        echo "ok: $titulo"
    fi
}

# 1. segredo
achou "token da Meta"            'EAA[A-Za-z0-9]{20,}'
achou "app secret / chave longa" '[a-f0-9]{32}'
achou "chave de servico"         '(service_role|secret_key|sk_live|refresh_token)[[:space:]]*[:=][[:space:]]*[A-Za-z0-9._-]{20,}'
achou "chave privada"            'BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY'

# 2. identificador real
achou "conta de anuncio"         'act_[0-9]{6,}'
achou "id longo da Meta"         '\b[0-9]{15,17}\b'
achou "MCC do Google Ads"        '\b[0-9]{3}-[0-9]{3}-[0-9]{4}\b'

# 3. dado de cliente (EDITE ESTA LISTA)
CLIENTES='nome-de-cliente-1|nome-de-cliente-2'
achou "nome de cliente"          "$CLIENTES"
achou "telefone BR"              '\b(\+?55)?[[:space:]]?\(?[1-9]{2}\)?[[:space:]]?9?[0-9]{4}-?[0-9]{4}\b'

# 4. autoteste: planta uma isca num arquivo NOVO e exige que o scrub a encontre.
# Sem isto, uma regressao no comando de busca transforma este script num carimbo
# de "limpo" que nao olhou nada. Carimbo falso e pior que nao ter script.
isca=".scrub-autoteste.tmp"
printf 'EAA%s\n' 'AUTOTESTEDOSCRUBISTONAOEUMTOKEN123456' > "$isca"
if git grep --untracked -qIiE 'EAA[A-Za-z0-9]{20,}' -- "$isca" 2>/dev/null; then
    echo "ok: autoteste (o scrub enxerga arquivo novo)"
else
    echo "FALHOU: autoteste -- o scrub NAO enxerga arquivo novo. Nao confie nele."
    falhou=1
fi
rm -f "$isca"

echo
if [ "$falhou" -eq 0 ]; then
    echo "limpo. pode empurrar."
else
    echo "NAO EMPURRE. Resolva os itens acima."
fi
exit "$falhou"
