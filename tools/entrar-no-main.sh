#!/usr/bin/env bash
# entrar-no-main.sh — põe o commit local no main sem depender de rebase limpo.
#
# POR QUE EXISTE (medido em 31/10/2026): sete workflows escrevem no main, cada um com o seu
# laço "rebase e tenta de novo". Rebase é a ferramenta errada quando os dois lados REGERAM o
# mesmo arquivo: marketing.html, publicacoes.json, posts/log.md saem diferentes a cada run, e o
# rebase para em conflito todas as vezes. Foi assim que o ciclo das 21h ficou vermelho duas
# vezes seguidas (runs 41128039668 e 41128399021 — "3 tentativas e o ciclo não entrou no main"),
# com o log do ciclo preso dentro do run.
#
# O que ele faz, em ordem, por tentativa:
#   1. fetch origin main;
#   2. tenta rebase — caminho barato, quando não há conflito;
#   3. se o rebase parar em conflito, desfaz e faz MERGE. Conflito em arquivo GERADO é resolvido
#      pelo próprio gerador: fica a versão do main e, logo depois, $GERAR reescreve o arquivo a
#      partir da fonte (posts/, docs/). Arquivo gerado não tem informação própria — quem tem é a
#      fonte dele;
#   4. conflito em arquivo que NÃO é gerado (código, workflow, documento escrito à mão) NÃO é
#      resolvido no chute: o merge é desfeito e o script sai com 1 dizendo qual arquivo é.
#
# Uso:
#   tools/entrar-no-main.sh "motivo do commit"
# Variáveis:
#   GERAR="python3 tools/melhorias.py && python3 tools/publicacoes.py"   (opcional)
#   TENTATIVAS=6                                                         (opcional)
set -uo pipefail

MOTIVO="${1:-artefatos da casa}"
TENTATIVAS="${TENTATIVAS:-6}"
: "${GERAR:=}"

# Só estes caminhos podem ser resolvidos automaticamente, porque são SAÍDA de gerador.
GERADOS='^(marketing\.html|melhorias\.html|publicacoes\.html|postar\.html|canais\.html|vitrina\.html|comite\.html|sitemap\.xml|index\.html|blog/|posts/[^/]+\.(json|md)|docs/PUBLICACOES\.md)$'

log() { echo "  [$MOTIVO] $*"; }

# DEFEITO CONHECIDO DA CASA: sem user.name/user.email o `git commit` morre com "empty ident
# name" — e aqui isso apareceria como "push recusado", escondendo a causa. Se o workflow não
# configurou identidade, o script configura uma, em vez de falhar por motivo invisível.
[ -n "$(git config user.name || true)" ] || git config user.name "casa-rebocl"
[ -n "$(git config user.email || true)" ] || git config user.email "casa@rebocl.local"

regerar() {
  [ -z "$GERAR" ] && return 0
  log "regerando: $GERAR"
  bash -c "$GERAR" >/dev/null 2>&1 || log "aviso: gerador saiu com erro (o arquivo do main fica)"
  git add -u >/dev/null 2>&1 || true
}

commit_do_merge() {
  if ! git diff --cached --quiet; then
    git commit -q -m "$MOTIVO: merge com o main" >/dev/null 2>&1 || true
  elif ! git rev-parse -q --verify MERGE_HEAD >/dev/null; then
    : # nada pendente
  fi
  if git rev-parse -q --verify MERGE_HEAD >/dev/null 2>&1; then
    git commit -q --no-edit >/dev/null 2>&1 || true
  fi
}

resolver_conflitos() {
  local sobra="" f
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    if printf '%s' "$f" | grep -Eq "$GERADOS"; then
      # fica a versão do main (o gerador reescreve logo depois, se a fonte mudou)
      git checkout --theirs -- "$f" 2>/dev/null || git checkout --ours -- "$f" 2>/dev/null || true
      git add -- "$f" >/dev/null 2>&1 || true
      log "conflito em arquivo gerado: $f (fica a versão do main; o gerador reescreve)"
    else
      sobra="$sobra $f"
    fi
  done < <(git diff --name-only --diff-filter=U)
  SOBRA="$sobra"
  [ -z "$sobra" ]
}

SOBRA=""
for n in $(seq 1 "$TENTATIVAS"); do
  if ! git fetch -q origin main; then
    log "fetch falhou (tentativa $n)"; sleep $((n * 3)); continue
  fi

  # 1. caminho barato: rebase sem conflito
  if git rebase -q origin/main >/dev/null 2>&1; then
    regerar
    git commit -q --amend --no-edit >/dev/null 2>&1 || true
    if git push -q origin HEAD:main 2>/dev/null; then
      log "no main por rebase (tentativa $n)"; exit 0
    fi
    log "push recusado depois do rebase (tentativa $n)"
    sleep $((n * 3)); continue
  fi
  git rebase --abort >/dev/null 2>&1 || true

  # 2. merge: resolve gerado, reescreve pela fonte, recusa o resto
  if git merge --no-edit origin/main >/dev/null 2>&1; then
    regerar
    commit_do_merge
    if git push -q origin HEAD:main 2>/dev/null; then
      log "no main por merge (tentativa $n)"; exit 0
    fi
    log "push recusado depois do merge (tentativa $n)"
  elif resolver_conflitos; then
    regerar
    commit_do_merge
    if git push -q origin HEAD:main 2>/dev/null; then
      log "no main por merge resolvido nos gerados (tentativa $n)"; exit 0
    fi
    log "push recusado depois do merge resolvido (tentativa $n)"
  else
    log "conflito em arquivo que NÃO é gerado:$SOBRA — não sobrescrevo; desfaço o merge"
    git merge --abort >/dev/null 2>&1 || true
    exit 1
  fi
  sleep $((n * 3))
done

log "não entrou no main em $TENTATIVAS tentativas"
exit 1
