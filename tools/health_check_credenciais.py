"""Quais credenciais o auditor de camadas mede.

Fonte única para os contratos: a lista sai do PRÓPRIO auditor (camadas do tipo `credencial`),
não de uma cópia mantida à mão. Uma lista paralela diverge — e foi exatamente uma divergência
dessas que fez o `health-check` dizer "44/44 ativas" e o `status-total` dizer "43/44" no mesmo
minuto, sobre o mesmo repositório (17/11/2026).
"""
import json
import os
import subprocess

# Segredos operacionais: os workflows precisam deles para agir (disparar outro workflow, assinar
# OAuth), mas o auditor não os trata como camada. Declarados aqui para não virarem "esquecidos".
OPERACIONAIS = ("X_API_KEY", "X_API_SECRET", "X_ACCESS_TOKEN", "X_ACCESS_TOKEN_SECRET", "GHPAT")


def credenciais_auditadas(caminho_auditor, env=None):
    codigo = ("const hc=require(process.env.HC);"
              "process.stdout.write(JSON.stringify("
              "hc.CAMADAS.filter(c=>c.tipo==='credencial').map(c=>c.nome)))")
    saida = subprocess.run(["node", "-e", codigo], capture_output=True, text=True, timeout=60,
                           env={**os.environ, "HC": os.path.abspath(caminho_auditor),
                                **(env or {})})
    try:
        declaradas = json.loads(saida.stdout or "[]")
    except ValueError:
        declaradas = []
    return sorted(set(declaradas) | set(OPERACIONAIS))
