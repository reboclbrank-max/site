# site

Site oficial da **Rebocl Brank — Jogos e Aplicativos**.

- Ao vivo: https://reboclbrank-max.github.io/site
- Arquivo único `index.html` com CSS embutido, sem dependências externas.
- Documentação e histórico: repositório privado `base`.

## Nota de espaço (2026-09-16)
O `ceifalume/index.wasm` (35 MB) não fica no espaço de trabalho — ele vive
neste repositório. Para rodar o trio/servidor local, traga de volta com:
`git checkout -- ceifalume/index.wasm`
Nunca commitar a remoção: o wasm pertence ao HEAD (o site ao vivo usa ele).

## Pasta media/ (2026-09-18)
`media/ceifalume/` hospeda as imagens de divulgação hotlinkadas na descrição
da página da itch.io (via `<img>`): GIF de 14 s (640×360) e screenshot.
Regra: URL pública e estável — **não apagar/renomear** arquivo que a
descrição da itch aponte (se precisar, atualizar a descrição da itch antes).
