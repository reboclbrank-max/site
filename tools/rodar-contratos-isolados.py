#!/usr/bin/env python3
"""Contratos em cópia descartável, sem segredos nem saída de rede externa.
O checkout que será publicado nunca recebe efeitos de teste em posts/.
"""
from pathlib import Path
import os,re,shutil,subprocess,sys,tempfile
IGNORAR=shutil.ignore_patterns('.git','node_modules','__pycache__','.venv','build','.cache','.env','.token*')
GUARDA_PY='''import socket
_original=socket.socket.connect
def conectar(self,address):
 if isinstance(address,tuple) and str(address[0]) not in ('127.0.0.1','localhost','::1'):raise RuntimeError('CONTRATO_REDE_EXTERNA_BLOQUEADA')
 return _original(self,address)
socket.socket.connect=conectar
'''
GUARDA_JS="const n=require('net'),o=n.Socket.prototype.connect;n.Socket.prototype.connect=function(...a){let x=a[0];if(Array.isArray(x))x=x[0];const h=x&&typeof x==='object'?x.host:(typeof a[1]==='string'?a[1]:'localhost');if(h&&!['localhost','127.0.0.1','::1'].includes(String(h)))throw Error('CONTRATO_REDE_EXTERNA_BLOQUEADA');return o.apply(this,a);};"
def rodar(raiz,nome):
 if nome.startswith("tools/"):nome=nome[6:]
 if not re.fullmatch(r'testes-[a-z0-9-]+\.(py|js)',nome) or not(raiz/'tools'/nome).is_file():raise ValueError('contrato não permitido')
 with tempfile.TemporaryDirectory(prefix='contrato-isolado-') as tmp:
  tmp=Path(tmp);copia=tmp/'site';shutil.copytree(raiz,copia,ignore=IGNORAR)
  guarda=tmp/'guarda';guarda.mkdir();(guarda/'sitecustomize.py').write_text(GUARDA_PY);(guarda/'rede.cjs').write_text(GUARDA_JS)
  env={k:os.environ[k] for k in ['HOME','PATH','LANG','LC_ALL','TMPDIR','FFMPEG_PATH'] if k in os.environ}
  env['PYTHONPATH']=str(guarda);env['NODE_OPTIONS']='--require '+str(guarda/'rede.cjs')
  cmd=[sys.executable if nome.endswith('.py') else 'node',str(copia/'tools'/nome)]
  return subprocess.run(cmd,cwd=copia,env=env,timeout=150).returncode

def main(nomes):
 raiz=Path(__file__).resolve().parents[1]
 if not nomes:nomes=[f.name for f in sorted((raiz/'tools').glob('testes-*')) if f.suffix in ('.py','.js')]
 for nome in nomes:
  try:code=rodar(raiz,nome)
  except Exception as e:print('Contrato isolado não aprovado:',type(e).__name__);return 1
  if code:return code
 print('Contratos isolados aprovados; checkout original preservado.')
 return 0
if __name__=='__main__':sys.exit(main(sys.argv[1:]))
