import importlib.util
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
P=Path(__file__).parent

def carregar(nome):
 s=importlib.util.spec_from_file_location(nome,P/(nome+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
M=carregar('conciliar-estado');L=carregar('loop-24h');G=carregar('testes-entrar-no-main')
class Conciliacao(unittest.TestCase):
 def test_duas_tarefas_novas_nao_se_perdem(self):
  self.assertEqual({x['id'] for x in M.conciliar([], [{'id':'A'}],[{'id':'B'}])},{'A','B'})
 def test_campos_independentes(self):
  self.assertEqual(M.conciliar({'a':1,'b':1},{'a':2,'b':1},{'a':1,'b':2}),{'a':2,'b':2})
 def test_duas_versoes_incompativeis_nao_escolhe_uma(self):
  with self.assertRaises(M.Conflito):M.conciliar({'estado':'pendente'},{'estado':'entregue'},{'estado':'falhou'})
 def test_mesmo_id_alteracoes_disjuntas(self):
  b=[{'id':'A','estado':'pendente','nota':''}]
  r=M.conciliar(b,[{'id':'A','estado':'entregue','nota':''}],[{'id':'A','estado':'pendente','nota':'observação'}])
  self.assertEqual(r,[{'id':'A','estado':'entregue','nota':'observação'}])
 def test_id_duplicado_recusa(self):
  with self.assertRaises(M.Conflito):M.conciliar([], [{'id':'A'},{'id':'A'}],[{'id':'B'}])
 def test_remocao_concorrente_com_edicao_recusa(self):
  with self.assertRaises(M.Conflito):M.conciliar({'a':1},{},{'a':2})
 def test_log_append_preserva_ambos(self):self.assertEqual(M.texto('base\n','base\nA\n','base\nB\n'),'base\nB\nA\n')
 def test_lista_append_preserva(self):self.assertEqual(M.conciliar([1],[1,2],[1,3]),[1,3,2])
 def test_helper_git_real_preserva_duas_filas(self):
  with tempfile.TemporaryDirectory() as t:
   _,a,b=G.montar(t)
   G.outro_escritor(b,'posts/fila-tarefas.json','{"tarefas":[{"id":"B"}]}\n','B')
   G.escrever(str(Path(a)/'posts/fila-tarefas.json'),'{"tarefas":[{"id":"A"}]}\n')
   G.git(a,'add','-A',check=True);G.git(a,'commit','-qm','A',check=True)
   r=G.rodar_helper(a,gerar='');self.assertEqual(r.returncode,0,r.stdout+r.stderr)
   data=json.loads(G.git(b,'show','origin/main:posts/fila-tarefas.json').stdout) if False else json.loads(G.git(a,'show','HEAD:posts/fila-tarefas.json').stdout)
   self.assertEqual({x['id'] for x in data['tarefas']},{'A','B'})
 def test_gerador_falhando_nao_publica(self):
  with tempfile.TemporaryDirectory() as t:
   _,a,b=G.montar(t);antes=G.git(b,'rev-parse','HEAD').stdout
   G.escrever(str(Path(a)/'posts/log.md'),'- ciclo 1\n- novo\n');G.git(a,'add','-A',check=True);G.git(a,'commit','-qm','novo',check=True)
   self.assertNotEqual(G.rodar_helper(a,gerar='false').returncode,0)
   G.git(b,'fetch','-q','origin','main',check=True);self.assertEqual(G.git(b,'rev-parse','origin/main').stdout,antes)
 def test_loop_falha_nao_e_sucesso(self):
  with patch.object(L,'rodar',return_value=(1,'falhou')),patch.object(L,'commitar',return_value=(False,'falhou')),patch.object(L.os.path,'exists',return_value=False):
   self.assertEqual(L.main(['--pulsos','1']),1)
 def test_commit_falhando_nao_significa_nada_a_commitar(self):
  with patch.object(L,'rodar',side_effect=[(0,''),(1,''),(1,'commit falhou')]):self.assertFalse(L.commitar('teste')[0])
 def test_push_falhando_nao_confirma(self):
  with patch.object(L,'rodar',side_effect=[(0,''),(1,''),(0,''),(1,'push falhou')]):self.assertFalse(L.commitar('teste')[0])
if __name__=='__main__':unittest.main()
