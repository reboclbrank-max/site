from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class Dependencias(unittest.TestCase):
 def test_pillow_antes_da_barreira(self):
  texto=(ROOT/'.github/workflows/postagem-diaria.yml').read_text()
  self.assertLess(texto.index('pip install --disable-pip-version-check Pillow==12.0.0'),texto.index('- name: Barreira offline de autonomia e marca'))
  self.assertIn('testes-gif-com-selo.py',texto)
 def test_pillow_real_disponivel(self):
  from PIL import Image
  self.assertEqual(Image.new('RGB',(2,2)).size,(2,2))
if __name__=='__main__':unittest.main()
