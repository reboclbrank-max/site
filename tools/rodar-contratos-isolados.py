#!/usr/bin/env python3
"""Contratos em cópia descartável, sem segredos nem saída de rede externa.
O checkout que será publicado nunca recebe efeitos de teste em posts/.

Uso:
  python3 tools/rodar-contratos-isolados.py                      # roda todos os contratos de tools/
  python3 tools/rodar-contratos-isolados.py tools/testes-x.py     # roda um contrato
  python3 tools/rodar-contratos-isolados.py tools/testes-x.py ARG # roda um contrato passando ARG a ele
"""
from pathlib import Path
import os,re,shutil,subprocess,sys,tempfile,traceback
IGNORAR=shutil.ignore_patterns('.git','node_modules','__pycache__','.venv','build','.cache','.env','.token*')
GUARDA_PY='''import socket
_original=socket.socket.connect
def conectar(self,address):
 if isinstance(address,tuple) and str(address[0]) not in ('127.0.0.1','localhost','::1'):raise RuntimeError('CONTRATO_REDE_EXTERNA_BLOQUEADA')
 return _original(self,address)
socket.socket.connect=conectar
'''
GUARDA_JS="const n=require('net'),o=n.Socket.prototype.connect;n.Socket.prototype.connect=function(...a){let x=a[0];if(Array.isArray(x))x=x[0];const h=x&&typeof x==='object'?x.host:(typeof a[1]==='string'?a[1]:'localhost');if(h&&!['localhost','127.0.0.1','::1'].includes(String(h)))throw Error('CONTRATO_REDE_EXTERNA_BLOQUEADA');return o.apply(this,a);};"

def rodar(raiz,nome,extra=()):
 """Executa um contrato em cópia descartável. `extra` vai como argv do contrato."""
 if nome.startswith("tools/"):nome=nome[6:]
 if not re.fullmatch(r'testes-[a-z0-9-]+\.(py|js)',nome) or not(raiz/'tools'/nome).is_file():raise ValueError('contrato não permitido: '+nome)
 with tempfile.TemporaryDirectory(prefix='contrato-isolado-') as tmp:
  tmp=Path(tmp);copia=tmp/'site';shutil.copytree(raiz,copia,ignore=IGNORAR)
  guarda=tmp/'guarda';guarda.mkdir();(guarda/'sitecustomize.py').write_text(GUARDA_PY);(guarda/'rede.cjs').write_text(GUARDA_JS)
  env={k:os.environ[k] for k in ['HOME','PATH','LANG','LC_ALL','TMPDIR','FFMPEG_PATH'] if k in os.environ}
  env['PYTHONPATH']=str(guarda);env['NODE_OPTIONS']='--require '+str(guarda/'rede.cjs')
  cmd=[sys.executable if nome.endswith('.py') else 'node',str(copia/'tools'/nome)]+[str(a) for a in extra]
  # devolve só o código: `rodar` é chamado por contrato (testes-bancada-isolada.py)
  return subprocess.run(cmd,cwd=copia,env=env,timeout=150).returncode

def separar(raiz,nomes):
 """Separa nomes de contrato de argumentos. Nome de contrato é o que existe em tools/ e casa
 com testes-*.py|js; todo o resto é argumento (ex.: o caminho do vídeo em gravar-gameplay)."""
 contratos=[];extras=[]
 for n in nomes:
  base=n[6:] if n.startswith('tools/') else n
  if re.fullmatch(r'testes-[a-z0-9-]+\.(py|js)',base) and (raiz/'tools'/base).is_file():
   contratos.append(base)
  else:
   extras.append(n)
 return contratos,extras

def main(nomes):
 raiz=Path(__file__).resolve().parents[1]
 # 04/11/2026 — DIAGNÓSTICO E ARGUMENTOS.
 # Antes: qualquer argumento extra era tratado como nome de contrato, o `rodar` recusava
 # com ValueError('contrato não permitido') e o `main` imprimia apenas o NOME da exceção.
 # Resultado: `gravar-gameplay` falhou 6 execuções seguidas sem dizer nada além de
 # "Contrato isolado não aprovado: ValueError".
 # Agora: vários contratos continuam aceitos (é como a barreira offline chama);
 # argumentos são repassados quando há exatamente UM contrato; toda falha mostra o motivo.
 if not nomes:
  alvos=[f.name for f in sorted((raiz/'tools').glob('testes-*')) if f.suffix in ('.py','.js')]
  extra=[]
 else:
  alvos,extra=separar(raiz,nomes)
 if not alvos:print('nenhum contrato encontrado em: '+' '.join(nomes),file=sys.stderr);return 1
 if extra and len(alvos)!=1:
  print('argumentos extras exigem exatamente um contrato; recebidos '+str(len(alvos))+' contratos e '+str(len(extra))+' argumento(s): '+' '.join(extra),file=sys.stderr);return 1
 for nome in alvos:
  try:code=rodar(raiz,nome,extra)
  except Exception as e:
   print('Contrato isolado não aprovado: '+type(e).__name__+': '+str(e),file=sys.stderr)
   traceback.print_exc()
   return 1
  if code:
   print('Contrato isolado reprovado: '+str(nome)+' (código '+str(code)+')',file=sys.stderr)
   return code
 print('Contratos isolados aprovados; checkout original preservado.')
 return 0

if __name__=='__main__':sys.exit(main(sys.argv[1:]))
