#!/usr/bin/env bash
# Scrub: nada de segredo nem de dado de cliente entra neste repo.
#
# Rode ANTES de todo push. Sai 0 quando esta limpo, 1 quando achou algo.
#   ./scripts/scrub.sh
#
# Se voce forkou isto pra sua operacao, edite CLIENTES abaixo com os nomes
# reais da SUA carteira. E o unico jeito de o scrub te proteger de verdade:
# regex generico nao sabe que "Acme Pneus" e cliente seu.

set -uo pipefail
cd "$(dirname "$0")/.."

falhou=0

achou() {   # <titulo> <regex>
    local titulo="$1" regex="$2"
    local hits
    hits=$(git grep -nIiE "$regex" -- . ':!scripts/scrub.sh' 2>/dev/null \
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

echo
if [ "$falhou" -eq 0 ]; then
    echo "limpo. pode empurrar."
else
    echo "NAO EMPURRE. Resolva os itens acima."
fi
exit "$falhou"
