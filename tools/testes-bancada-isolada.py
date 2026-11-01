import importlib.util,pathlib,tempfile,unittest,os
p=pathlib.Path(__file__).with_name('rodar-contratos-isolados.py');spec=importlib.util.spec_from_file_location('bancada',p);B=importlib.util.module_from_spec(spec);spec.loader.exec_module(B)
class Bancada(unittest.TestCase):
 def caso(self,codigo):
  with tempfile.TemporaryDirectory() as d:
   r=pathlib.Path(d);(r/'tools').mkdir();(r/'posts').mkdir();f=r/'posts/fila.json';f.write_text('DADO_REAL');(r/'tools/testes-sujo.py').write_text(codigo);antes=os.environ.get('TOKEN_BANCADA_SENTINELA');os.environ['TOKEN_BANCADA_SENTINELA']='privado'
   try:code=B.rodar(r,'testes-sujo.py')
   finally:
    if antes is None:os.environ.pop('TOKEN_BANCADA_SENTINELA',None)
    else:os.environ['TOKEN_BANCADA_SENTINELA']=antes
   self.assertEqual(f.read_text(),'DADO_REAL');return code
 def test_escrita_nao_altera_checkout(self):self.assertEqual(self.caso("from pathlib import Path;Path('posts/fila.json').write_text('FIXTURE_PUBLICAR')"),0)
 def test_falha_tambem_nao_altera_checkout(self):self.assertEqual(self.caso("from pathlib import Path;Path('posts/fila.json').write_text('FIXTURE');raise SystemExit(7)"),7)
 def test_sem_segredo_herdado(self):self.assertEqual(self.caso("import os;assert 'TOKEN_BANCADA_SENTINELA' not in os.environ"),0)
 def test_rede_externa_bloqueada(self):self.assertEqual(self.caso("import socket\ntry:socket.create_connection(('192.0.2.1',443))\nexcept RuntimeError as e:assert 'BLOQUEADA' in str(e)\nelse:raise SystemExit(1)"),0)
 def test_nome_arbitrario_recusado(self):
  with self.assertRaises(ValueError):B.rodar(pathlib.Path('.'),'../../publicar.py')
if __name__=='__main__':unittest.main()
