// generic.html: brand names that became ordinary words. Reuses esc() and legend() from shared.js.
import {esc,legend} from './shared.js';
export {esc,legend};

/* Both colours pass 4.5:1 as text on white (#c1281e 5.9:1, #8a6500 5.3:1). */
export const GEN_GROUPS = {
  lost:{label:'Lost',color:'#c1281e',note:'The trademark is legally generic, or has lapsed, in at least one major country.'},
  slipping:{label:'Slipping',color:'#8a6500',note:'Still a protected trademark, but widely used as an everyday word.'}};

/* Region filter: derived from the free-text region string. An entry can match several (e.g. "US, UK"). */
export const REGIONS = {global:'Worldwide',na:'US & Canada',uk:'UK & Ireland',anz:'Australia & NZ'};
export function regionKeys(r){const s=String(r||'').toLowerCase(),k=[];
  if(s==='global')return ['global'];
  if(/\b(us|canada)\b/.test(s))k.push('na');
  if(/\b(uk|ireland)\b/.test(s))k.push('uk');
  if(/australia|new zealand/.test(s))k.push('anz');
  return k}

export async function loadGeneric(){const r=await fetch(new URL('generic.json',import.meta.url));
  if(!r.ok)throw new Error(`generic.json: HTTP ${r.status}`);
  const d=await r.json();if(!Array.isArray(d.entries))throw new Error('generic.json has no entries');
  d.entries.sort((a,b)=>a.word.localeCompare(b.word));d.entries.forEach(e=>e._r=regionKeys(e.region));return d}

const pct=s=>Math.round(s*100)+'%';
const POS={noun:'n.',verb:'v.',both:'n. & v.'};
const NS='http://www.w3.org/2000/svg';
function el(n,a={},p){const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);p&&p.append(e);return e}

/* Tooltip (pointer only; everything in it is also in the dictionary entry, so it is hidden from assistive tech). */
let tip;
function showTip(html,x,y){if(!tip){tip=document.createElement('div');tip.className='tip';tip.setAttribute('aria-hidden','true');document.body.append(tip)}
  tip.innerHTML=html;tip.style.display='block';const w=tip.offsetWidth,h=tip.offsetHeight;
  tip.style.left=Math.max(6,Math.min(innerWidth-w-6,x+14))+'px';tip.style.top=(y-h-12<6?y+16:y-h-12)+'px'}
export function hideTip(){if(tip)tip.style.display='none'}
export function tipHTML(e){const g=GEN_GROUPS[e.status];
  return `<b>${esc(e.brand)}</b> <span style="opacity:.7">${esc(e.owner)}, ${esc(e.launch_year)}</span>`+
    `<div>${esc(e.word)}: ${esc(e.meaning)}</div><div style="opacity:.8">${esc(e.note)}</div>`+
    `<div style="opacity:.7">${g?esc(g.label):''} · ${e.lower_share_recent==null?'no 2010s data':pct(e.lower_share_recent)+' lowercase in the 2010s'}</div>`}

/* Scatter: x = launch year, y = lowercase share in the 2010s. Dots are not tab stops; the list below carries the same data. */
export function scatter(host,entries,{height=520,ink='#16130f',grid='#0000001a'}={}){
  host.innerHTML='';const pts=entries.filter(e=>e.lower_share_recent!=null&&e.launch_year!=null);
  const W=Math.max(300,host.clientWidth||700),H=height,m={t:30,r:16,b:46,l:42};
  const lo=Math.floor(Math.min(1900,...pts.map(e=>e.launch_year))/10)*10,hi=2010;
  const X=y=>m.l+(y-lo)/(hi-lo)*(W-m.l-m.r),Y=s=>H-m.b-s*(H-m.t-m.b);
  const nL=pts.filter(e=>e.status==='lost').length,nM=pts.filter(e=>e.lower_share_recent>=.5).length;
  const svg=el('svg',{viewBox:`0 0 ${W} ${H}`,width:'100%',role:'img','aria-label':`Scatter of ${pts.length} brand names: launch year against the share of printed uses written in lowercase in the 2010s. ${nM} are lowercase more often than not; ${nL} are lost trademarks. Every entry is listed in the dictionary below.`},host);
  for(const s of[0,.25,.5,.75,1]){el('line',{x1:m.l,x2:W-m.r,y1:Y(s),y2:Y(s),stroke:s===.5?ink:grid,'stroke-dasharray':s===.5?'3 4':'',opacity:s===.5?.45:1},svg);
    const t=el('text',{x:m.l-7,y:Y(s)+4,'text-anchor':'end',fill:ink,'font-size':11,opacity:.65},svg);t.textContent=s*100+'%'}
  const half=el('text',{x:W-m.r-4,y:Y(.5)-6,'text-anchor':'end',fill:ink,'font-size':11,'font-style':'italic',opacity:.7},svg);half.textContent='half lowercase';
  const step=W<560?50:25;for(let y=Math.ceil(lo/step)*step;y<=hi;y+=step){el('line',{x1:X(y),x2:X(y),y1:H-m.b,y2:H-m.b+4,stroke:ink,opacity:.4},svg);const t=el('text',{x:X(y),y:H-m.b+17,'text-anchor':'middle',fill:ink,'font-size':11,opacity:.65},svg);t.textContent=y}
  const ax=el('text',{x:(W+m.l-m.r)/2,y:H-6,'text-anchor':'middle',fill:ink,'font-size':12},svg);ax.textContent='Year the brand launched →';
  const yt=el('text',{x:m.l,y:12,fill:ink,'font-size':12},svg);yt.textContent=W<560?'↑ Lowercase share, 2010s':'↑ Share of printed uses written in lowercase, 2010s';
  const r=W>1000?4.2:3.6,big=W>1000;
  const dots=el('g',{},svg);
  pts.forEach((e,i)=>{const c=GEN_GROUPS[e.status]?.color||ink,cx=X(e.launch_year),cy=Y(e.lower_share_recent);
    el('circle',{cx,cy,r:e.status==='lost'?r:r*.85,fill:c,opacity:e.status==='lost'?.95:.75,stroke:'#fff','stroke-width':1,'pointer-events':'none'},dots);
    el('circle',{cx,cy,r:11,fill:'transparent','data-i':i,style:'cursor:pointer'},dots)});
  const on=ev=>{const i=ev.target.dataset?.i;if(i==null)return;const b=ev.target.getBoundingClientRect();showTip(tipHTML(pts[i]),b.left+b.width/2,b.top+b.height/2)};
  dots.addEventListener('pointerover',on);dots.addEventListener('pointerout',hideTip);
  dots.addEventListener('pointerdown',ev=>{if(ev.pointerType!=='mouse')on(ev)});
  // Greedy labels: lost first, then the most-printed; skip a label only if every nearby slot collides.
  const fs=big?11:10,box=[],hit=a=>a.x<m.l||a.x+a.w>W-m.r||a.y<16||a.y+a.h>H-m.b||box.some(b=>a.x<b.x+b.w&&b.x<a.x+a.w&&a.y<b.y+b.h&&b.y<a.y+a.h);
  for(const e of pts){box.push({x:X(e.launch_year)-3,y:Y(e.lower_share_recent)-3,w:6,h:6})}
  box.push({x:m.l,y:0,w:330,h:18},{x:W-m.r-110,y:Y(.5)-18,w:110,h:14});
  const rank=e=>(e.status==='lost'?1e9:0)+(e.total_recent_per_million||0);
  for(const e of[...pts].sort((a,b)=>rank(b)-rank(a))){const cx=X(e.launch_year),cy=Y(e.lower_share_recent),w=e.word.length*fs*.56+2,h=fs+1;
    const near=[[cx+6,cy-h/2],[cx-6-w,cy-h/2],[cx-w/2,cy-6-h],[cx-w/2,cy+6],[cx+5,cy-h-3],[cx+5,cy+3],[cx-5-w,cy-h-3],[cx-5-w,cy+3]];
    for(let R=14;R<=50;R+=6)for(let k=0;k<16;k++){const t=k/16*2*Math.PI;near.push([cx+R*Math.cos(t)-(Math.cos(t)<0?w:0),cy+R*Math.sin(t)-h/2])}
    const at=near.map(([x,y])=>({x,y,w,h})).find(a=>!hit(a));if(!at)continue;box.push(at);
    const lx=at.x>cx?at.x:at.x+w>cx?cx:at.x+w,ly=at.y+h/2;if(Math.hypot(lx-cx,ly-cy)>13)el('line',{x1:cx,y1:cy,x2:lx,y2:ly,stroke:ink,'stroke-width':.5,opacity:.35,'pointer-events':'none'},svg);
    const t=el('text',{x:at.x,y:at.y+h-2,fill:ink,'font-size':fs,'font-weight':e.status==='lost'?700:400,opacity:e.status==='lost'?1:.75,'pointer-events':'none'},svg);t.textContent=e.word}
  return entries.filter(e=>!pts.includes(e))}

/* Inline sparkline of lowercase share by decade, 1900s-2010s on a shared axis, with the 50% line marked. */
const DEC=[];for(let d=1900;d<=2010;d+=10)DEC.push(d);
export function spark(e){const col=GEN_GROUPS[e.status]?.color||'#111',w=84,h=20,p=2.5,X=i=>p+i*(w-2*p)/(DEC.length-1),Y=s=>h-p-s*(h-2*p);
  let d='',on=false,last=null;DEC.forEach((y,i)=>{const v=e.decades?.[y]?.lower_share;if(v==null){on=false;return}d+=(on?'L':'M')+X(i).toFixed(1)+' '+Y(v).toFixed(1);on=true;last=[X(i),Y(v)]});
  const ks=Object.keys(e.decades||{}).filter(k=>e.decades[k].lower_share!=null).sort();
  const r=e.lower_share_recent,since=e.first_decade_majority_lower;
  const label=r==null?'No lowercase data for the 2010s':`Lowercase in ${pct(r)} of printed uses in the 2010s`+(ks.length>1?`, from ${pct(e.decades[ks[0]].lower_share)} in the ${ks[0]}s`:'')+(since?`; the majority since the ${since}s`:'');
  return `<span class="sp"><svg width="${w}" height="${h}" viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc(label)}"><title>${esc(label)}</title>`+
    `<rect x="0" y="0" width="${w}" height="${h}" fill="#f4f4f4"/><line x1="0" x2="${w}" y1="${Y(.5)}" y2="${Y(.5)}" stroke="#111" stroke-opacity=".45" stroke-dasharray="2 2"/>`+
    (d?`<path d="${d}" fill="none" stroke="${col}" stroke-width="1.6" stroke-linejoin="round" stroke-linecap="round"/>`:'')+
    (last?`<circle cx="${last[0].toFixed(1)}" cy="${last[1].toFixed(1)}" r="2.2" fill="${col}"/>`:'')+
    `</svg><span aria-hidden="true">${r==null?'no data':pct(r)+' lowercase'}</span></span>`}

export function entryHTML(e){const g=GEN_GROUPS[e.status]||{label:e.status,color:'#666'};
  const by=`${esc(e.brand)}${e.owner&&e.owner!==e.brand?' ('+esc(e.owner)+', '+esc(e.launch_year)+')':' ('+esc(e.launch_year)+')'}`;
  const lost=e.status==='lost'&&e.lost_year?` Trademark lost ${esc(e.lost_year)}.`:'';
  const reg=e.region&&e.region!=='global'?`<span class="reg">${esc(e.region)}</span>`:'';
  const pref=e.generic_term&&e.generic_term.toLowerCase()!==e.word.toLowerCase()?` The owner would say <i>${esc(e.generic_term)}</i>.`:'';
  const src=/^https?:\/\//.test(e.source_url||'')?` <a class="src" href="${esc(e.source_url)}" rel="noopener noreferrer">source</a>`:'';
  return `<div class="e"><span class="hw">${esc(e.word)}</span> <span class="pos">${esc(POS[e.pos]||e.pos)}</span> ${esc(e.meaning)}. <span class="etym">From ${by}.${lost}</span>`+
    `<span class="tag" style="color:${g.color}">${esc(g.label)}</span>${reg}`+
    `<span class="small">${esc(e.note)}${pref}${src}</span>${spark(e)}</div>`}

export const GEN_METHODS=`<p><b>Lowercase share</b> is the share of a word's printed uses in Google Books (English, 1900 to 2019) written entirely in lowercase: <i>zipper</i> rather than <i>Zipper</i> or <i>ZIPPER</i>. Writers lowercase a word when they treat it as the ordinary name of a thing rather than as a brand, so a rising share is a sign the name is turning generic. The dashed line marks half.</p>
<p>The share is a lower bound. Every sentence that starts with the word is capitalised, so even a fully generic word never reaches 100%. Names that are also surnames or places, such as Hoover, are pulled down further by every Mr Hoover. Edited books follow style guides that keep trademark capitals, and printed text lags speech by years, so a word can be everyday talk long before books show it.</p>
<p>Decades before a brand launched are left out. Counts for rare words are small and noisy; a sparkline that sits at zero can mean the word is simply rare in print.</p>
<p><b>Lost</b> means a court, registry or lapse made the trademark generic in at least one major country; it may still be protected elsewhere (Aspirin is still a Bayer trademark in some countries). <b>Slipping</b> means it is still protected but widely used as the everyday word. The region is where the generic use is documented. Status and notes are editorial summaries of the linked sources, not legal advice.</p>`;
