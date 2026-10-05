# Site — Rebocl Brank

Site público da **Rebocl Brank — Jogos e Aplicativos**.

- **Ao vivo:** https://reboclbrank-max.github.io/site/
- **Hospedagem:** GitHub Pages pela raiz; a página usa `index.html`, CSS embutido e não depende de CDN.
- **Documentação de marca, jogos e operação:** repositório privado [`base`](https://github.com/reboclbrank-max/base).

## Ceifalume 0.1

O diretório `ceifalume/` contém o **export web gerado** a partir do repositório privado `reboclbrank-max/ceifalume`; não edite o export manualmente. Gere-o pelo pipeline documentado em `base/projetos/01-ceifalume/progresso.md`, confira os arquivos e só publique com autorização aplicável.

A [release pública `v0.1`](https://github.com/reboclbrank-max/site/releases/tag/v0.1) reúne estes assets: `ceifalume-0.1-web.zip` (13.035.144 bytes), `ceifalume-trailer-0.1.mp4` (3.473.373 bytes) e `ceifalume.apk` (83.579.693 bytes). Não substitua nem remova assets publicados sem autorização e sem atualizar os links que os utilizam.

### Arquivos do export web

No estado de `main` auditado em **2026-10-05**, `ceifalume/index.wasm` tem **38.047.590 bytes** no repositório (tamanho bruto; o tamanho transferido pode ser diferente por compressão HTTP). Se o arquivo não estiver na cópia de trabalho local, restaure-o do Git com `git checkout -- ceifalume/index.wasm`; **não comite sua remoção**. Para medir o download real, confira a resposta HTTP atual em vez de inferi-lo pelo tamanho do arquivo bruto.

## Mídia de divulgação

`media/ceifalume/` hospeda imagens estáveis hotlinkadas na página da itch.io e usadas nos posts. A captura `shot-dia9-chuva-1280x720.png`, correspondente ao Post 6, foi adicionada em **2026-10-03**. URLs públicas podem estar embutidas em páginas e posts: não apague nem renomeie os arquivos sem atualizar primeiro os links dependentes.

## Organização do repositório

- `index.html` — home do site.
- `ceifalume/` — export web gerado.
- `media/ceifalume/` — assets estáveis de divulgação.
- `privacidade.html`, `app-ads.txt`, `sitemap.xml`, `robots.txt` — arquivos de suporte do site.

O README é documentação do repositório; não é uma alteração do conteúdo da página. Mudanças em `index.html`, na exportação do jogo, em releases ou em mídia pública precisam de verificação própria e autorização explícita.
