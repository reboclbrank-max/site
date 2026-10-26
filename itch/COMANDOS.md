# Comandos prontos — sem caçar cookie, sem DevTools de cookies

O Console fica **ao lado** da aba Elementos, no mesmo painel que você já abriu.
Se o Chrome reclamar de colar código, digite `allow pasting` e Enter.

## 1. Ler o que está na página hoje (comando curto)

Na página `https://itch.io/game/edit/5017404`, cole isto no Console e aperte Enter:

```js
(()=>{const f=[...document.querySelectorAll('form')].find(x=>x.querySelector('[name=csrf_token]'));if(!f)return alert('Abra a página de edição do jogo primeiro.');const o={};['title','short_text','description','genre','tags','min_price','classification'].forEach(n=>{const e=f.querySelector('[name='+n+']');if(e)o[n]=e.value});prompt('Copie tudo e me mande:',JSON.stringify(o,null,1))})()
```

Abre uma caixa com o conteúdo atual. Copie e mande. **Nada é gravado.**

## 2. Aplicar o conteúdo publicado (comando longo)

O mesmo código do favorito, em versão para Console — está em `itch/comando-console.txt`.
Ele busca `posts/pagina-itch.json`, mostra antes/depois e **só grava se você confirmar**.

## 3. Favorito (permanente, sem DevTools)

`itch/preencher-bookmarklet.txt` — crie um favorito com essa linha. Um clique na página de
edição e ele faz o mesmo que o comando do item 2.

## 0. O endereço da página de edição (descoberto em 26/10 no navegador do dono)

**É este:** `https://itch.io/game/edit/5017404`

O padrão é `/game/edit/<id do jogo>`. O `/dashboard/game/<id>/edit` que eu tinha suposto dá 404 —
o itch não documenta isso e, fora da sessão, todos os formatos dão 404. Por isso o código agora
descobre o caminho pela própria sessão (`tools/itch-navegador.py`, `descobrir_edicao`).

## 0b. Se algum dia mudar de novo

O endereço do editor não é documentado e devolve 404 para quem não tem sessão — testados e
descartados em 26/10: `/game/edit/<id>`, `/dashboard/game/<id>`, `/dashboard/games/<id>`,
`/game/<id>/edit`, `/my-game/<id>/edit`, `/dashboard/project/<id>/edit`, `<jogo>/edit`.

Com a sessão aberta, em **qualquer** página do itch, cole isto no Console:

```js
(()=>{const l=[...document.querySelectorAll('a')].map(a=>a.getAttribute('href')||'').filter(h=>h.includes('/dashboard'));const ed=l.find(h=>/\/edit/.test(h));if(ed){location.href=ed;return 'abrindo '+ed}if(l.length){if(window.copy)copy(l.join('\n'));prompt('Não achei "edit". Copiei os links do dashboard — me mande:',l.join('\n'));return}prompt('Nenhum link de dashboard aqui. Vá em Dashboard → clique no Ceifalume → Edit e me mande o endereço.')})()
```

Se ele disser "abrindo …", você está na página certa e o resto (`itch/comando-console.txt`)
funciona. Se ele mostrar links, me mande — com o endereço real eu conserto `!itch pagina` e o
favorito de vez.

## 1b. Ler todos os campos da página de edição (versão que funciona)

A página tem **vários** formulários (o de busca do topo também tem `csrf_token`), então escolher
"o primeiro form" devolve vazio. Esta versão varre a página inteira:

```js
(()=>{const c=[...document.querySelectorAll('input[name],textarea[name],select[name]')].filter(e=>!/csrf|password|_token/i.test(e.name));const o={};c.forEach(e=>{o[e.name]=e.type==='checkbox'?e.checked:String(e.value||'').slice(0,400)});const t=JSON.stringify(o,null,1);if(window.copy)copy(t);alert('achei '+c.length+' campos: '+Object.keys(o).slice(0,10).join(', '));console.log(t);return t})()
```

Depois de rodar, **Ctrl+V no chat** cola o conteúdo (ele já vai para a área de transferência).
Nada é gravado.

## 4. Preencher o gênero (comando testado em navegador)

Hoje `game[genre]` está `none` — é o único campo vazio da página. Este comando escolhe
"Simulation" pelo rótulo, mostra `antes -> depois` e só envia se você confirmar.
Está em `itch/comando-genero.txt`.

```js
(()=>{const t=document.querySelector('[name="game[title]"]');if(!t)return alert('Esta não é a página de edição (sem game[title]).');const f=t.form;const e=f.querySelector('[name="game[genre]"]');if(!e)return alert('Esta página não tem o campo de gênero.');const antes=e.options[e.selectedIndex].textContent.trim();const alvo=[...e.options].find(o=>o.textContent.trim().toLowerCase()==='simulation');if(!alvo){alert('Opções de gênero: '+[...e.options].map(o=>o.textContent.trim()).join(', '));return 'sem opcao'}e.value=alvo.value;e.dispatchEvent(new Event('change',{bubbles:true}));if(!confirm('Gênero: '+antes+' -> '+alvo.textContent.trim()+'. Salvar?'))return 'cancelado';const b=f.querySelector('[type="submit"]');if(b)b.click();else f.submit();return 'enviado'})()
```

**Testado** em navegador com um formulário igual ao do itch (Chromium 156, headless):
o envio levou `game[genre]=sim`, manteve `csrf_token` e os demais campos, e as travas
("sem game[title]", "sem campo de gênero") disparam corretamente.

> Regra nova do repositório: **todo comando entregue ao dono passa por `node --check`**
> antes de sair (`tools/testes-bookmarklet-itch.js`). Foi assim que um `...` literal meu
> derrubou dois comandos seguidos — não acontece mais sem a barreira pegar.
