# Comandos prontos — sem caçar cookie, sem DevTools de cookies

O Console fica **ao lado** da aba Elementos, no mesmo painel que você já abriu.
Se o Chrome reclamar de colar código, digite `allow pasting` e Enter.

## 1. Ler o que está na página hoje (comando curto)

Na página `https://itch.io/dashboard/game/5017404/edit`, cole isto no Console e aperte Enter:

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

## 0. Achar e abrir a página de edição (o endereço varia e não é adivinhável)

O endereço do editor não é documentado e devolve 404 para quem não tem sessão — testados e
descartados em 26/10: `/dashboard/game/<id>/edit`, `/dashboard/game/<id>`, `/dashboard/games/<id>`,
`/game/<id>/edit`, `/my-game/<id>/edit`, `/dashboard/project/<id>/edit`, `<jogo>/edit`.

Com a sessão aberta, em **qualquer** página do itch, cole isto no Console:

```js
(()=>{const l=[...document.querySelectorAll('a')].map(a=>a.getAttribute('href')||'').filter(h=>h.includes('/dashboard'));const ed=l.find(h=>/\/edit/.test(h));if(ed){location.href=ed;return 'abrindo '+ed}if(l.length){if(window.copy)copy(l.join('\n'));prompt('Não achei "edit". Copiei os links do dashboard — me mande:',l.join('\n'));return}prompt('Nenhum link de dashboard aqui. Vá em Dashboard → clique no Ceifalume → Edit e me mande o endereço.')})()
```

Se ele disser "abrindo …", você está na página certa e o resto (`itch/comando-console.txt`)
funciona. Se ele mostrar links, me mande — com o endereço real eu conserto `!itch pagina` e o
favorito de vez.
