#!/usr/bin/env python3
"""Merge de três vias: preserva mudanças independentes; ambiguidade não é sobrescrita.
JSON por campos e listas com ID; listas/textos append-only. Sem rede/execução de ação.
"""
import json
from pathlib import Path
import subprocess
import sys

AUSENTE=object()
class Conflito(ValueError):pass

def conciliar(base, local, remoto):
    if local==remoto:return local
    if local==base:return remoto
    if remoto==base:return local
    if isinstance(local,dict) and isinstance(remoto,dict) and (isinstance(base,dict) or base is AUSENTE):
        b={} if base is AUSENTE else base;out={}
        for k in sorted(b.keys()|local.keys()|remoto.keys()):
            v=conciliar(b.get(k,AUSENTE),local.get(k,AUSENTE),remoto.get(k,AUSENTE))
            if v is not AUSENTE:out[k]=v
        return out
    if isinstance(local,list) and isinstance(remoto,list) and (isinstance(base,list) or base is AUSENTE):
        b=[] if base is AUSENTE else base
        if all(isinstance(x,dict) and isinstance(x.get('id'),(str,int)) for x in b+local+remoto):
            def indice(xs):
                d={x['id']:x for x in xs}
                if len(d)!=len(xs):raise Conflito('IDs duplicados')
                return d
            bm,lm,rm=indice(b),indice(local),indice(remoto);res=[]
            for k in dict.fromkeys([x['id'] for x in remoto+local+b]):
                v=conciliar(bm.get(k,AUSENTE),lm.get(k,AUSENTE),rm.get(k,AUSENTE))
                if v is not AUSENTE:res.append(v)
            return res
        if local[:len(b)]==b and remoto[:len(b)]==b:
            res=list(remoto)
            for x in local[len(b):]:
                if x not in res[len(b):]:res.append(x)
            return res
    raise Conflito('alterações concorrentes incompatíveis')

def texto(base,local,remoto):
    if local==remoto:return local
    if local==base:return remoto
    if remoto==base:return local
    if local.startswith(base) and remoto.startswith(base):
        extra=local[len(base):]
        return remoto if extra in remoto[len(base):] else remoto+extra
    raise Conflito('texto não append-only')

def versao(n,caminho):
    r=subprocess.run(['git','show',f':{n}:{caminho}'],capture_output=True)
    return r.stdout.decode('utf-8') if r.returncode==0 else None

def main(caminho):
    if not caminho.startswith('posts/') or Path(caminho).suffix not in ('.json','.md') or '..' in Path(caminho).parts:
        raise Conflito('fora do contrato')
    b,l,r=[versao(n,caminho) for n in (1,2,3)]
    if l is None or r is None:raise Conflito('remoção em conflito exige revisão')
    if caminho.endswith('.json'):
        out=conciliar(json.loads(b) if b is not None else AUSENTE,json.loads(l),json.loads(r))
        resultado=json.dumps(out,ensure_ascii=False,indent=1)+'\n'
    else:resultado=texto(b or '',l,r)
    f=Path(caminho);tmp=f.with_name(f.name+'.merge-tmp');tmp.write_text(resultado,encoding='utf-8');tmp.replace(f)
if __name__=='__main__':
    try:main(sys.argv[1])
    except Exception as e:print('conciliação recusada:',type(e).__name__);sys.exit(1)
