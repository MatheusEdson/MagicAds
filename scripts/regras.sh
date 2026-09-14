#!/usr/bin/env bash
# As regras, num lugar so. Sourcado por scripts/scrub.sh (arvore de trabalho)
# e por scripts/historico.sh (todo blob de todo commit).
#
# POR QUE ISTO E UM ARQUIVO SEPARADO: ter duas listas de regras em dois scripts
# garante que uma hora uma regra entra numa e nao na outra. E nao falha
# barulhento -- falha calada, dizendo "limpo" sobre o que nunca olhou.

# ---------------------------------------------------------------------------
# permitido(): o trecho CASADO e placeholder declarado?
#
# Vale pro TRECHO, nunca pra linha inteira. A versao anterior descartava a
# linha toda se ela contivesse "exemplo" em qualquer posicao. Num repo escrito
# em portugues, inteiro construido em cima de `exemplos/`, essa e a palavra
# mais comum que existe. Efeito medido:
#
#     # exemplo de configuracao
#     TOKEN=EAA<token de verdade>        ->  scrub dizia "limpo. pode empurrar."
#
# Um token real passava por escrever "exemplo" na linha de cima.
# ---------------------------------------------------------------------------
permitido() {
    case "$1" in
        *xxxxxxxx*|*XXXXXXXX*)         return 0 ;;
        *00000000*)                    return 0 ;;
        *exemplo*|*EXEMPLO*|*Exemplo*) return 0 ;;
        *placeholder*|*PLACEHOLDER*)   return 0 ;;
        # Sequencia de digitos de manual, ANCORADA. Como `*1234567890*` solto
        # ela liberava qualquer coisa que a contivesse -- inclusive um token
        # de 40 caracteres que por acaso tivesse essa sequencia no meio.
        # Descoberto plantando a isca `EAA...1234567890`: a varredura de
        # historico disse "LIMPO" sobre um token que estava la.
        1234567890|0123456789)         return 0 ;;
        act_1234567890|act_0123456789) return 0 ;;
        123-456-7890)                  return 0 ;;
        # RFC 5737 / RFC 3849: faixas que existem PARA documentacao. Usar 1.2.3.4
        # de exemplo e apontar pra maquina de alguem.
        127.0.0.1|0.0.0.0|1.2.3.4)     return 0 ;;
        192.0.2.*|198.51.100.*|203.0.113.*) return 0 ;;
        # Senha de DSN que e a propria palavra "senha"/"password". Troca
        # consciente e estreita: so libera quando a senha E o placeholder. Uma
        # senha de verdade (`:Xk9#2p@`) continua reprovando. O risco que sobra e
        # o DSN cuja senha real seja literalmente "senha" -- e quem tem essa
        # senha tem um problema maior que este script.
        *:senha@*|*:SENHA@*|*:password@*|*:PASSWORD@*|*:pass@*) return 0 ;;
    esac
    return 1
}

# ---------------------------------------------------------------------------
# REGRAS: "titulo|regex". Uma entrada por classe de vazamento.
# ---------------------------------------------------------------------------
REGRAS=(
    # -- 1. segredo
    "token da Meta|EAA[A-Za-z0-9]{20,}"
    # \b nas duas pontas: sem isso, qualquer SHA de git de 40 caracteres citado
    # num CHANGELOG vira alarme falso, e alarme falso e como scrub morre.
    "app secret / chave longa|\b[a-f0-9]{32}\b"
    "chave de servico|(service_role|secret_key|sk_live|refresh_token)[[:space:]]*[:=][[:space:]]*[A-Za-z0-9._-]{20,}"
    "chave privada|BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY"
    "senha em DSN|(postgres|postgresql|mysql|mongodb)(\+srv)?://[^:/@[:space:]]+:[^@[:space:]]{4,}@"

    # -- 2. identificador real
    "conta de anuncio|act_[0-9]{6,}"
    "id longo da Meta|\b[0-9]{15,17}\b"
    "MCC do Google Ads|\b[0-9]{3}-[0-9]{3}-[0-9]{4}\b"
    # O customer id do Google tambem circula CRU, sem hifen. A regra de telefone
    # pegava por coincidencia de formato, e regra de telefone e a primeira a ser
    # afrouxada no primeiro falso positivo chato.
    "customer id cru|\b[0-9]{10}\b"

    # -- 3. dado de cliente (o nome vem da lista local, mais abaixo)
    "telefone BR|\b(\+?55)?[[:space:]]?\(?[1-9]{2}\)?[[:space:]]?9?[0-9]{4}-?[0-9]{4}\b"

    # -- 4. infra interna
    # Caminho de maquina e IP nao sao segredo, mas desenham onde voce opera, e
    # e o tipo de linha que entra num comentario de debug e nunca mais sai.
    "IP|\b([0-9]{1,3}\.){3}[0-9]{1,3}\b"
    "caminho de maquina|(/root/|/home/[a-z]|[A-Za-z]:\\Users\\|/var/www/)"
)

# ---------------------------------------------------------------------------
# A lista de nomes de cliente NAO mora aqui: num repo publico, escrever os
# nomes dos seus clientes dentro do scrub e vazar exatamente o que ele existe
# pra proteger. Ela mora num arquivo local, ignorado pelo git.
# ---------------------------------------------------------------------------
LISTA="${MAGICADS_SCRUB_CLIENTES:-.scrub-clientes.local}"
CLIENTES=""
if [ -f "$LISTA" ]; then
    CLIENTES=$(grep -vE '^[[:space:]]*(#|$)' "$LISTA" | tr '\n' '|' | sed 's/|$//')
    # \b nas duas pontas. Sem isso um nome curto vira alarme em palavra comum:
    # um nome de 5 letras da lista casou com uma palavra maior dentro do proprio
    # CHANGELOG e travou o push por causa de uma frase em portugues.
    if [ -n "$CLIENTES" ]; then
        CLIENTES="\b($CLIENTES)\b"
        REGRAS+=("nome de cliente|$CLIENTES")
    fi
fi

aviso_sem_lista() {
    # Dois motivos diferentes, e confundi-los custa caro: arquivo ausente e
    # esperado no primeiro clone; arquivo presente e sem nome nenhum quer dizer
    # que alguem editou e o esvaziou sem perceber.
    if [ -f "$LISTA" ]; then
        echo "AVISO: nome de cliente NAO checado. $LISTA existe mas nao tem"
        echo "       nome nenhum (so comentario ou linha em branco)."
        echo "       Abra o arquivo e tire o # das linhas de nome, ou escreva"
        echo "       os seus. O modelo ja mostra o formato."
    else
        echo "AVISO: nome de cliente NAO checado: $LISTA nao existe."
        echo "       cp .scrub-clientes.local.exemplo .scrub-clientes.local"
    fi
    echo "       Um nome por linha nesse arquivo. Ele e ignorado pelo git, entao"
    echo "       os nomes ficam na sua maquina. Regex generico nao sabe que"
    echo "       \"Acme Pneus\" e cliente seu -- so essa lista sabe."
}
