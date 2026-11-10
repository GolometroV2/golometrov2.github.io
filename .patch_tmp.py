p = 'index.html'
s = open(p, encoding='utf-8').read()
fn = '''
// «Sin capitán»: cómo quedaría la tabla si el brazalete no diera puntos extra (suma de las jornadas jugadas)
function pintarSinCap() {
  const cont = $("#sincap"); if (!cont || !D || !D.matchdays) return;
  const R = D.managers.map((m, i) => {
    let tot = 0, ext = 0, n = 0;
    Object.values(D.matchdays).forEach(j => { const x = j && j[m.id]; if (!x || !capNum(x.points)) return; tot += x.points; n++;
      const c = x.captain; if (c && capNum(c.basePoints)) ext += c.basePoints * ((c.multiplier || 2) - 1); });
    return { m, i, tot, ext, sin: tot - ext, n };
  }).filter(r => r.n > 0);
  if (R.length < 3) { cont.innerHTML = ""; cont.hidden = true; return; }
  cont.hidden = false;
  const pos = (k, q) => { const o = R.slice().sort((a, b) => b[k] - a[k]); R.forEach(r => { r[q] = o.indexOf(r) + 1; }); return o; };
  pos("tot", "p0"); const sinOrd = pos("sin", "p1");
  const mx = Math.max(1, ...R.map(r => r.tot));
  const filas = sinOrd.map(r => { const d = r.p0 - r.p1;
    return `<li>${avatar(r.m, r.i)}<span class="pq"><b>${r.p1}.º ${esc(r.m.name)}</b><span class="pb" role="img" aria-label="${r.sin} puntos sin capitán, ${r.tot} con capitán"><i style="width:${Math.max(0, r.sin / mx * 100).toFixed(1)}%;background:${col(r.i)}"></i></span><small>${r.ext} pts del capitán · hoy ${r.p0}.º</small></span>
      <span class="pts"><b>${r.sin}</b><em class="${d > 0 ? "up" : d < 0 ? "dn" : ""}">${d > 0 ? "▲ " + d : d < 0 ? "▼ " + -d : "="}</em></span></li>`; }).join("");
  const cambian = R.filter(r => r.p1 !== r.p0).length, ayuda = R.slice().sort((a, b) => b.ext - a.ext)[0];
  cont.innerHTML = `<div class="gh"><h2>¿Y si no hubiera capitán?</h2></div>
    <p class="note" style="margin:0 0 10px">La tabla quitando los puntos extra del brazalete en todas las jornadas jugadas. La flecha dice cuántos puestos ganaría o perdería cada uno frente a la clasificación real.</p>
    <ul class="pron">${filas}</ul>
    <p class="note">${cambian ? `Cambiarían de puesto ${cambian} managers.` : "Nadie cambiaría de puesto: el capitán no decide la liga."} Al que más le ha dado el capitán: <b>${esc(ayuda.m.name)}</b> (+${ayuda.ext}).</p>`;
}
'''
k = '/* ---------- Premios de la temporada ---------- */'
assert k in s
s = s.replace(k, fn + '\n' + k, 1)
a = '<section class="card" id="rach"></section>'
assert a in s
s = s.replace(a, a + '\n    <section class="card" id="sincap"></section>', 1)
b = '  pintarRachas();\n  cuentaClasificacion();'
assert b in s
s = s.replace(b, '  pintarRachas();\n  pintarSinCap();\n  cuentaClasificacion();', 1)
c = '["premios", "🏅", "Premios"'
assert c in s
s = s.replace(c, '["sincap", "🎖️", "Sin capitán", "La tabla sin los puntos extra del brazalete"], ' + c, 1)
open(p, 'w', encoding='utf-8').write(s)
a = s.rfind('<script>'); b = s.find('</script>', a)
open('.t.js', 'w', encoding='utf-8').write(s[a + 8:b])
