(() => {
  const cont = document.querySelector('.container'), $ = (t, p = {}, ...h) => { const e = Object.assign(document.createElement(t), p); e.append(...h); return e; };
  document.head.append($('style', { textContent: `
  .tabs{max-width:1100px;margin:0 auto 14px;display:flex;gap:8px}.tabs button{background:#e2e8f0;color:#1e293b}.tabs button.on{background:#0f2942;color:#fff}
  .pan{display:none}.pan select{padding:8px;margin:0 8px 10px 0}.pan iframe{width:100%;height:calc(100vh - 150px);border:1px solid #cbd5e1;border-radius:8px}
  .gal{display:flex;gap:14px}.gr{flex:1;display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px;max-height:calc(100vh - 160px);overflow:auto;align-content:start}
  .gr figure{cursor:pointer;background:#fff;border:2px solid #cbd5e1;border-radius:6px;font-size:11px;padding:4px}.gr figure.no{border-color:#f59e0b}.gr img{width:100%;aspect-ratio:16/9;object-fit:cover}
  .tg{width:400px;max-height:calc(100vh - 160px);overflow:auto;font-size:12px;background:#fff;padding:10px;border:1px solid #cbd5e1}.tg img{width:100%}.tg td{padding:2px 6px;border-bottom:1px solid #eee;word-break:break-word}
  @media(max-width:800px){.gal{flex-direction:column}.tg{width:100%}}` }));
  const pm = $('div', { className: 'pan' }), pg = $('div', { className: 'pan' }), pp = $('div', { className: 'pan' }), pd = $('div', { className: 'pan' }), pans = [cont, pm, pg, pp, pd], nav = $('div', { className: 'tabs' });
  cont.before(nav); cont.after(pm, pg, pp, pd); const fp = $('iframe'), fd = $('iframe'); pp.append(fp); pd.append(fd);
  const sels = [pm, pg].map(p => { const s = $('select'); p.append(s); return s; }), info = $('span'), abrir = $('button', { textContent: 'Abrir carpeta', className: 'btn-secondary', style: 'flex:none;max-width:140px' });
  const fr = $('iframe'), gr = $('div', { className: 'gr' }), tg = $('div', { className: 'tg', textContent: 'Elige una imagen para ver sus tags.' });
  pm.append(fr); pg.append(abrir, ' ', info, $('div', { className: 'gal' }, gr, tg));
  let carpeta = null, pedido = 0;
  abrir.onclick = () => carpeta && abrirCarpeta(carpeta);
  const mapa = m => { fr.src = `/vuelos/${encodeURIComponent(m)}/visor.html`; };
  async function tags(m, f) {
    tg.textContent = 'Leyendo tags...';
    try {
      const r = await fetch(`/api/vuelos/${m}/tags/${f.n}`); if (!r.ok) throw Error(r.status);
      const t = await r.json(), tb = $('table'), img = $('img', { src: `/vuelos/${m}/miniaturas/${f.n}`, title: 'Abrir original' });
      img.onclick = () => open(`/vuelos/${m}/fotos/${f.n}`);
      for (const [k, v] of Object.entries(t)) tb.append($('tr', {}, $('td', { textContent: k }), $('td', { textContent: v })));
      tg.replaceChildren(img, $('b', { textContent: f.n }), tb);
    } catch (e) { tg.textContent = 'No se pudieron leer los tags: ' + e.message; }
  }
  async function galeria(m) {
    const id = ++pedido; gr.replaceChildren(); carpeta = null; info.textContent = 'Cargando...';
    try {
      const r = await fetch(`/api/vuelos/${m}/fotos`); if (!r.ok) throw Error(r.status);
      const d = await r.json(); if (id !== pedido) return; carpeta = d.carpeta + '/fotos';
      info.textContent = `${d.fotos.length} imágenes, ${d.fotos.filter(f => f.lat !== null).length} con GPS (borde naranja = sin GPS) | ${carpeta}`;
      for (const f of d.fotos) {
        const g = $('figure', { className: f.lat === null ? 'no' : '' }, $('img', { loading: 'lazy', src: `/vuelos/${m}/miniaturas/${f.n}` }), f.n);
        g.onclick = () => tags(m, f); gr.append(g);
      }
    } catch (e) { info.textContent = 'No se pudo cargar: ' + e.message; }
  }
  const carga = [null, mapa, galeria];
  [1, 2].forEach(i => sels[i - 1].onchange = e => { sels[2 - i].value = e.target.value; carga[i](e.target.value); });
  async function ir(i) {
    pans.forEach((p, k) => p.style.display = k === i ? 'block' : 'none'); [...nav.children].forEach((b, k) => b.classList.toggle('on', k === i));
    location.hash = ['', 'mapa', 'imagenes', 'plan', 'drones'][i]; if (!i) return; if (i === 3) { if (!fp.src) fp.src = '/static/plan.html'; return; } if (i === 4) { if (!fd.src) fd.src = '/static/drones.html'; return; }
    const g = await (await fetch('/api/vuelos_grupos')).json(), NG = { f450_gopro: 'F450 + GoPro', dji_mini2se: 'DJI Mini 2 SE' }, v = Object.values(g).flat(), act = sels[i - 1].value;
    sels.forEach(s => { s.replaceChildren(...Object.entries(g).map(([k, l]) => $('optgroup', { label: NG[k] || k }, ...l.map(n => $('option', { value: n, textContent: n }))))); s.value = v.includes(act) ? act : v[0] || ''; });
    if (sels[i - 1].value) carga[i](sels[i - 1].value);
  }
  ['Control', 'Vuelos y mapa', 'Imágenes y tags', 'Plan de vuelo', 'Vuelos DJI'].forEach((t, i) => nav.append($('button', { textContent: t, onclick: () => ir(i) })));
  ir(Math.max(0, ['', '#mapa', '#imagenes', '#plan', '#drones'].indexOf(location.hash)));
})();
