// Shared data helpers and hand-written SVG charts for every design.
export const GROUPS = {taken:{label:'Taken',color:'#d0342c',note:'The brand comes to mind first. The old meaning is rare.'},
  contested:{label:'Contested',color:'#b98700',note:'Both meanings are in daily use.'},
  failed:{label:'Kept',color:'#0e8a5f',note:'The word still means what it meant.'},
  watching:{label:'Watching',color:'#7a5ae0',note:'Too little data to call yet.'}};
const fiction=e=>e.brand_type==='character'||e.brand_type==='work';
export const isName=e=>/^\p{Lu}/u.test(e.word);
export const KINDS = {name:'Names',common:'Common words',rare:'Rare words'};
export async function load(){const d=await(await fetch(new URL('data.json', import.meta.url))).json();
  d.entries.sort((a,b)=>a.word.localeCompare(b.word));d.by=Object.fromEntries(d.entries.map(e=>[e.word.toLowerCase(),e]));
  d.all=d.entries;d.entries=d.all.filter(e=>e.english);return d}  // English-only by default; the browser can switch to d.all
// Group colour is independent of which meaning is ahead.
export const shade=e=>GROUPS[e.group].color;
const ownerName=s=>String(s||'').toLowerCase().replace(/\b(incorporated|inc|corporation|corp|company|co|limited|ltd|llc|plc)\b\.?/g,'').replace(/[^\p{L}\p{N}]+/gu,' ').trim();
export const ownerNeeded=(brand,owner)=>{const b=ownerName(brand),o=ownerName(owner);return !!o&&!(' '+b+' ').includes(' '+o+' ')&&!(' '+o+' ').includes(' '+b+' ')};
export function headerOffset(){const header=document.querySelector('.title');if(header)new ResizeObserver(()=>document.documentElement.style.setProperty('--header-offset',(innerWidth<=700?16:header.getBoundingClientRect().height+20)+'px')).observe(header)}
export const brandLine=e=>`${esc(e.brand)}${ownerNeeded(e.brand,e.owner)?' ('+esc(e.owner)+')':''}, ${e.launch_year}`;
/* Hover text: taken -> the lost original meaning; failed -> the company that tried; contested -> whichever side is losing. */
/* Chart y: measured Wikipedia share, else the books estimate; null = not plotted. */
export const shareY=e=>e.brand_share??e.brand_share_est??null;
export function tipHTML(e){const w=`<b>${esc(e.word)}</b>`,o=`<div>${esc(e.original_meaning)}</div>`,b=`<div>${brandLine(e)}${e.reason?'. '+esc(e.reason):''}</div>`,
    f=(fiction(e)?`<div style="opacity:.7">${e.brand_type==='character'?'Fictional character':'Film, show or game'}</div>`:''),sh=f+(e.brand_share!=null?`<div style="opacity:.7">Brand share ${Math.round(e.brand_share*100)}% (Wikipedia)</div>`:e.brand_share_est!=null?`<div style="opacity:.7">Brand share about ${Math.round(e.brand_share_est*100)}% (books)</div>`:'')+(e.discontinued?`<div style="opacity:.7">Discontinued${e.end_year?' in '+e.end_year:''}</div>`:'')+(e.region?`<div style="opacity:.7">${GROUPS[e.group].label} <span style="color:#aaa;font-size:10px">${esc(e.region)}</span></div>`:'');
  if(e.group==='taken')return `${w} <span style="opacity:.7">once meant</span>${o}<div style="opacity:.7">Now ${brandLine(e)}</div>${sh}`;
  if(e.group==='failed')return `${w} <span style="opacity:.7">Kept</span>${b}${sh}`;
  if(e.group==='contested'){const brandLosing=e.winner==='original'||(e.winner!=='brand'&&(e.brand_share??.5)<.5);
    return brandLosing?`${w} <span style="opacity:.7">the brand is behind</span>${b}${sh}`:`${w} <span style="opacity:.7">the original is behind</span>${o}<div style="opacity:.7">Brand: ${brandLine(e)}</div>${sh}`}
  return `${w}${o}${b}${f}`}
export const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
export const num=n=>n==null?'—':Math.round(n).toLocaleString('en-US');
export const pct=n=>n==null?'—':(n>0?'+':n<0?'−':'')+Math.abs(n)+'%';
export function winner(e){return e.winner==='brand'?e.brand+' is ahead':e.winner==='original'?'The original word is ahead':'Roughly even'}
let tip;function tooltip(){if(!tip){tip=document.createElement('div');tip.className='tip';tip.setAttribute('role','status');document.body.append(tip)}return tip}
function showTip(html,x,y){const t=tooltip();t.innerHTML=html;t.style.display='block';const w=t.offsetWidth,h=t.offsetHeight;
  t.style.left=Math.max(6,Math.min(innerWidth-w-6,x+14))+'px';t.style.top=Math.max(6,y-h-12)+'px'}
function hideTip(){if(tip)tip.style.display='none'}
const NS='http://www.w3.org/2000/svg';
function el(n,a={},p){const e=document.createElementNS(NS,n);for(const k in a)e.setAttribute(k,a[k]);p&&p.append(e);return e}
function ticks(max,n=4){const s=Math.pow(10,Math.floor(Math.log10(max/n||1)));const m=[1,2,5,10].find(v=>v*s>=max/n)*s;const r=[];for(let v=0;v<=max+1e-9;v+=m)r.push(v);return r}
/* series: [{name, color, dash, points:{year:count}, label}] one y axis; a missing year stays a gap, never zero. */
/* tab:false keeps the chart out of the tab order (cards in a strip); right: right margin; s.fmt(y): tooltip value as HTML-safe text. */
export function lineChart(host,{series,mark,from,to,ink='#222',grid='#0000001a',height=300,endLabels=true,ring='#fff',tab=true,right}){
  host.innerHTML='';const W=Math.max(host.clientWidth<300?240:300,host.clientWidth||640),H=height,m={t:24,r:right??(W<480?62:96),b:28,l:46};
  const svg=el('svg',{viewBox:`0 0 ${W} ${H}`,width:'100%',role:'img','aria-label':series.map(s=>s.name).join(', ')+' by year'},host);
  const yr=[];for(let y=from;y<=to;y++)yr.push(y);
  const max=Math.max(...series.flatMap(s=>yr.map(y=>s.points[y]||0)),1);
  const X=y=>m.l+(y-from)/(to-from)*(W-m.l-m.r),Y=v=>H-m.b-v/max*(H-m.t-m.b);
  for(const v of ticks(max)){el('line',{x1:m.l,x2:W-m.r,y1:Y(v),y2:Y(v),stroke:grid},svg);const t=el('text',{x:m.l-7,y:Y(v)+4,'text-anchor':'end',fill:ink,'font-size':11,opacity:.65},svg);t.textContent=v.toLocaleString('en-US')}
  let step=(to-from)>16?5:(W<480?3:2);const px=(W-m.l-m.r)/(to-from);if(step*px<40)step=[10,20,25,50,100].find(v=>v*px>=40)||100;  // keep year labels apart on narrow charts
  for(const y of yr)if((step>=10?y:y-from)%step===0){const t=el('text',{x:X(y),y:H-8,'text-anchor':'middle',fill:ink,'font-size':11,opacity:.65},svg);t.textContent=y}
  if(mark&&mark.year>=from&&mark.year<=to){el('line',{x1:X(mark.year),x2:X(mark.year),y1:m.t-6,y2:H-m.b,stroke:ink,'stroke-dasharray':'2 3',opacity:.55},svg);const lft=X(mark.year)>W*.6,t=el('text',{x:X(mark.year)+(lft?-5:5),y:m.t-8,fill:ink,'font-size':11,'text-anchor':lft?'end':'start'},svg);t.textContent=mark.label}
  for(const s of series){let d='',on=false;for(const y of yr){const v=s.points[y];if(v==null){on=false;continue}d+=(on?'L':'M')+X(y).toFixed(1)+' '+Y(v).toFixed(1);on=true}
    el('path',{d,fill:'none',stroke:s.color,'stroke-width':2,'stroke-linecap':'round','stroke-linejoin':'round','stroke-dasharray':s.dash||''},svg);
    const ly=[...yr].reverse().find(y=>s.points[y]!=null);if(ly!=null){el('circle',{cx:X(ly),cy:Y(s.points[ly]),r:4,fill:s.color,stroke:ring,'stroke-width':2},svg);if(endLabels){const t=el('text',{x:X(ly)+8,y:Y(s.points[ly])+4,fill:ink,'font-size':12},svg);t.textContent=s.name}}}
  const cross=el('line',{y1:m.t,y2:H-m.b,stroke:ink,opacity:0},svg),hit=el('rect',{x:m.l,y:m.t,width:W-m.l-m.r,height:H-m.t-m.b,fill:'transparent',...(tab?{tabindex:0,'aria-label':'Explore values by year'}:{})},svg);
  const move=y=>{cross.setAttribute('x1',X(y));cross.setAttribute('x2',X(y));cross.setAttribute('opacity',.35);const r=svg.getBoundingClientRect(),k=r.width/W;
    showTip(`<b>${y}</b>`+series.map(s=>`<div>${esc(s.name)}: ${s.points[y]==null?'not published':s.fmt?s.fmt(y):num(s.points[y])}</div>`).join(''),r.left+X(y)*k,r.top+m.t*k+20)};
  let cur=to;const at=e=>{const r=svg.getBoundingClientRect();return Math.max(from,Math.min(to,Math.round(from+((e.clientX-r.left)*W/r.width-m.l)/(W-m.l-m.r)*(to-from))))};
  hit.addEventListener('pointermove',e=>move(cur=at(e)));hit.addEventListener('pointerleave',()=>{hideTip();cross.setAttribute('opacity',0)});
  hit.addEventListener('blur',()=>{hideTip();cross.setAttribute('opacity',0)});hit.addEventListener('keydown',e=>{if(e.key==='ArrowLeft'||e.key==='ArrowRight'){e.preventDefault();cur=Math.max(from,Math.min(to,cur+(e.key==='ArrowLeft'?-1:1)));move(cur)}});
  return svg}
/* x: how common the word was before launch (log scale), y: brand share (Wikipedia, else estimated from books). */
export function stealsChart(host,entries,{ink='#222',grid='#0000001a',height=460,labels=[],colors=true,onPick,corners=false,palette=null,ring='#fff',minViews=0,group='',plotLegend=false,search='',onJump}={}){
  hideTip();host.innerHTML='';const eligible=entries.filter(e=>(!group||e.group===group)&&e.pre_launch_per_million!=null&&shareY(e)!=null),pts=eligible.filter(e=>!minViews||(e.brand_views||0)>=minViews);
  const W=Math.max(300,host.clientWidth||700),H=height,m={t:44,r:18,b:44,l:48};
  const svg=el('svg',{viewBox:`0 0 ${W} ${H}`,width:'100%',role:'group','aria-label':'Word frequency before launch against brand share of attention today'},host);
  const lmin=-3,lmax=3,X=v=>m.l+(Math.max(lmin,Math.min(lmax,Math.log10(v)))-lmin)/(lmax-lmin)*(W-m.l-m.r),Y=s=>H-m.b-6-s*(H-m.t-m.b-12);
  const views=pts.map(e=>Math.max(0,e.brand_views||0)),vmin=views.length?Math.min(...views):0,vmax=views.length?Math.max(...views):0,p=.35;
  const PX=e=>X(e.pre_launch_per_million),PY=e=>Y(shareY(e)),size=v=>{const lo=W<560?2:2.5,hi=W<560?7:9,t=vmin===vmax?1:(Math.max(0,v||0)**p-vmin**p)/(vmax**p-vmin**p);return lo+t*(hi-lo)},radius=e=>size(e.brand_views);
  const extent=e=>radius(e)+(e.region?.6:0),phone=innerWidth<=600;
  for(const s of[0,.25,.5,.75,1]){el('line',{x1:m.l,x2:W-m.r,y1:Y(s),y2:Y(s),stroke:grid},svg);const t=el('text',{x:m.l-7,y:Y(s)+4,'text-anchor':'end',fill:ink,'font-size':11,opacity:.65},svg);t.textContent=s*100+'%'}
  for(let l=lmin;l<=lmax;l++){const t=el('text',{x:X(10**l),y:H-m.b+16,'text-anchor':'middle',fill:ink,'font-size':11,opacity:.65},svg);t.textContent=l===lmin?'≤'+10**l:10**l>=1?(10**l).toLocaleString('en-US'):String(10**l)}
  const ax=el('text',{x:(W+m.l-m.r)/2,y:H-6,'text-anchor':'middle',fill:ink,'font-size':12},svg);ax.textContent=W<560?'Book frequency before launch →':'Uses per million words in books before launch (log scale) →';
  const words=pts.filter(e=>!isName(e)).length,names=pts.filter(isName).length,books=pts.filter(e=>e.brand_share==null).length,discontinued=pts.filter(e=>e.discontinued).length;
  const legendRows=[['Mark',[['dot','Wikipedia'],['books','book estimate'],['hollow','discontinued'],['regional','regional']]]];
  const sizeItems=pts.length?[vmin,((vmin**p+vmax**p)/2)**(1/p),vmax].map((v,i)=>[size(v),i===0&&v<100?'under 100':Number(v.toPrecision(2)).toLocaleString('en-US')]):[];
  const query=search.trim().toLowerCase(),shape=e=>'dot',tags=e=>({'data-word':e.word.toLowerCase(),'data-shape':shape(e),'data-mark':(e.brand_share==null?'books':'dot')+(e.discontinued?' hollow':'')+(e.region?' regional':'')});
  let pinned=null,hover=null,focus=null;
  const filter=()=>{const f=hover||focus||pinned;hideTip();svg.querySelectorAll('[data-shape]').forEach(e=>{const hide=f&&!(e.getAttribute('data-'+f[0])||'').split(' ').includes(f[1]);e.style.opacity=hide?0:query&&e.dataset.word!==query? .12:'';e.style.pointerEvents=hide?'none':''})};
  const bindLegend=(e,row,k,label)=>{const f=[row.toLowerCase(),k];e.setAttribute('data-legend',k);e.setAttribute('tabindex',0);e.setAttribute('role','button');e.setAttribute('aria-label',`${row}: ${label}`);e.style.cursor='pointer';
    e.addEventListener('pointerenter',ev=>{if(ev.pointerType!=='touch'){hover=f;filter()}});e.addEventListener('pointerleave',()=>{hover=null;filter()});
    e.addEventListener('focus',()=>{focus=f;filter()});e.addEventListener('blur',()=>{focus=null;filter()});
    const toggle=()=>{pinned=pinned&&pinned[0]===f[0]&&pinned[1]===k?null:f;hover=focus=null;filter()};
    e.addEventListener('click',ev=>{ev.stopPropagation();toggle()});e.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();toggle()}})};
  svg.addEventListener('click',ev=>{if(!ev.target.closest('[data-shape],[data-legend]')){pinned=hover=focus=null;filter()}});
  const legendBox=null;
  const positions=new Map(),bind=(g,e,cx,cy,r)=>{positions.set(e,{cx,cy,r});let tapped=0;
    const on=()=>{const b=svg.getBoundingClientRect(),k=b.width/W;showTip(tipHTML(e)+(onJump?'<div style="opacity:.7">Tap or hover a marker for details; tap it again to open its dictionary entry.</div>':''),b.left+cx*k,b.top+cy*k)};
    g.addEventListener('pointerenter',ev=>{if(ev.pointerType!=='touch')on()});g.addEventListener('focus',on);g.addEventListener('pointerleave',hideTip);g.addEventListener('blur',hideTip);
    g.addEventListener('click',()=>{if(onJump){const now=Date.now();if(now-tapped<1800){hideTip();onJump(e);tapped=0;return}tapped=now;on()}else if(onPick)onPick(e);else on()});
    g.addEventListener('keydown',ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();if(onJump){hideTip();onJump(e)}else if(onPick)onPick(e);else on()}if(ev.key==='Escape')hideTip()})};
  for(const e of [...pts].sort((a,b)=>radius(b)-radius(a))){const g=el('g',{...tags(e),tabindex:0,role:'button',style:'cursor:pointer;touch-action:manipulation','aria-label':`${e.word}: ${GROUPS[e.group].label}${onJump?'. Press Enter for dictionary entry':''}`},svg);
    const cx=PX(e),cy=PY(e),r=radius(e),col=(palette&&palette[e.group])||shade(e);
    el('circle',{cx,cy,r:Math.max(12,extent(e)),fill:'transparent'},g);
    el('circle',{cx,cy,r,...markStyle(e.discontinued,col,e.brand_share==null,!!e.region,ink)},g);if(e.discontinued&&e.region)el('circle',{cx,cy,r:r+2,fill:'none',stroke:ink,'stroke-width':.6},g);bind(g,e,cx,cy,extent(e))}
  if(labels==='all'){ // greedy placement: taken first, then most-viewed; skip a label only if it would collide
    const fs=W>1000?11:10,box=legendBox?[legendBox]:[],hit=(a)=>a.x<m.l||a.x+a.w>W-m.r||a.y<15||a.y+a.h>H-m.b||box.some(b=>a.x<b.x+b.w&&b.x<a.x+a.w&&a.y<b.y+b.h&&b.y<a.y+a.h);
    const measure=word=>{const t=el('text',{'font-size':fs},svg);t.textContent=word;const w=t.getComputedTextLength()+3;t.remove();return w},few=pts.length<90,far=phone?60:few?120:60;for(const e of pts){const cx=PX(e),cy=PY(e),r=extent(e)+1;box.push({x:cx-r,y:cy-r,w:2*r,h:2*r})}
    const rank=e=>(e.group==='taken'?1e12:0)+(e.brand_views||0)+(e.original_views||0);
    box.push({x:m.l,y:0,w:250,h:16});if(corners)box.push({x:W-m.r-230,y:20,w:230,h:20},{x:m.l,y:20,w:210,h:20},{x:W-m.r-220,y:H-m.b-26,w:220,h:22});
    const ranked=[...pts].sort((a,b)=>phone?(b.brand_views||0)-(a.brand_views||0):rank(b)-rank(a));
    for(const e of phone?ranked.slice(0,10):ranked){if(e.word.toLowerCase()===query)continue;const cx=PX(e),cy=PY(e),r=extent(e),d=r+3,w=measure(e.word),h=fs+3;
      const near=[[cx+d,cy-h/2],[cx-d-w,cy-h/2],[cx-w/2,cy-d-h],[cx-w/2,cy+d],[cx+d,cy-h-d],[cx+d,cy+d],[cx-d-w,cy-h-d],[cx-d-w,cy+d]];for(let R=r+11;R<=far;R+=6)for(let i=0;i<16;i++){const t=i/16*2*Math.PI;near.push([cx+R*Math.cos(t)-(Math.cos(t)<0?w:0),cy+R*Math.sin(t)-h/2])}
      let at=near.map(([x,y])=>({x,y,w,h})).find(a=>!hit(a));if(!at){const free=[];for(let y=18;y+h<H-m.b;y+=h+2)for(let x=m.l;x+w<W-m.r;x+=8){const a={x,y,w,h};if(!hit(a))free.push(a)}at=free.sort((a,b)=>Math.hypot(a.x+w/2-cx,a.y+h/2-cy)-Math.hypot(b.x+w/2-cx,b.y+h/2-cy))[0]}if(!at)continue;box.push(at);{const lx=at.x>cx?at.x:at.x+w>cx?cx:at.x+w,ly=at.y+h/2;if(!phone&&Math.hypot(lx-cx,ly-cy)>13)el('line',{...tags(e),x1:cx,y1:cy,x2:lx,y2:ly,stroke:ink,'stroke-width':.5,opacity:.35,'pointer-events':'none'},svg)}
      const t=el('text',{...tags(e),x:at.x,y:at.y+h-2,fill:ink,'font-size':fs,opacity:.8,'pointer-events':'none'},svg);t.textContent=e.word}
  }else for(const w of labels){const e=pts.find(p=>p.word.toLowerCase()===w);if(!e||e.word.toLowerCase()===query)continue;const t=el('text',{...tags(e),x:PX(e)+extent(e)+4,y:PY(e)-extent(e)-3,fill:ink,'font-size':12,'font-weight':600,'pointer-events':'none'},svg);t.textContent=e.word}
  if(corners)for(const[x,y,a,t]of[[W-m.r-6,34,'end','Common word, now the brand\'s'],[m.l+8,34,'start','Rare word, now the brand\'s'],[W-m.r-6,H-m.b-10,'end','Common word, still its own']]){const c=el('text',{x,y,'text-anchor':a,fill:ink,'font-size':13,opacity:.6,'pointer-events':'none'},svg);c.textContent=t}
  const yt=el('text',{x:m.l,y:11,fill:ink,'font-size':12},svg);yt.textContent=W<560?'↑ Brand share':'↑ Brand share of attention today';
  let found=false;const match=pts.find(e=>e.word.toLowerCase()===query);
  if(query){svg.querySelectorAll('[data-word]').forEach(e=>{if(e.dataset.word!==query)e.style.opacity=.12});if(match){found=true;svg.append([...svg.querySelectorAll('g[tabindex][data-word]')].find(g=>g.dataset.word===query));const {cx,cy,r}=positions.get(match),g=el('g',{...tags(match),'pointer-events':'none'},svg);
    el('circle',{cx,cy,r:r+5,fill:'none',stroke:ink,'stroke-width':1.5},g);const w=match.word.length*7+8,x=Math.max(m.l,Math.min(W-m.r-w,cx-w/2)),y=Math.max(25,cy-r-11);
    el('rect',{x,y:y-12,width:w,height:16,fill:'var(--p, #fff)'},g);const t=el('text',{x:x+4,y,fill:ink,'font-size':12,'font-weight':600},g);t.textContent=match.word}}
  const off=entries.filter(e=>(!group||e.group===group)&&!eligible.includes(e));
  return {plotted:pts.length,total:eligible.length,found,words,names,books,discontinued,legendRows,sizeItems,bindLegend,legendInPlot:!!legendBox,off,noBooks:off.filter(e=>e.pre_launch_per_million==null).length}}
/* Circles: pale = books, hollow = discontinued, dark outline = regional. */
function mark(k,x,y,r){if(k==='square'){const d=r*Math.sqrt(Math.PI)/2;return `M${x-d} ${y-d}h${2*d}v${2*d}h${-2*d}Z`}if(k==='dot')return`M${x-r} ${y}a${r} ${r} 0 1 0 ${2*r} 0a${r} ${r} 0 1 0 ${-2*r} 0Z`;const d=r*Math.sqrt(Math.PI/2);
  return `M${x} ${y-d}L${x+d} ${y}L${x} ${y+d}L${x-d} ${y}Z`}
const markStyle=(gone,col,books,regional=false,ink=col)=>({fill:gone?'var(--p, #fff)':col,'fill-opacity':gone?1:books?.35:.85,...(gone||regional?{stroke:gone?col:regional?ink:col,'stroke-width':regional?1.2:1,'stroke-opacity':regional?1:books?.45:1,'stroke-linejoin':'round'}:{})});
export const MARK=(k,col,r=3.6)=>`<svg width="${Math.max(12,2*r+2)}" height="${Math.max(12,2*r+2)}" viewBox="${-Math.max(6,r+1)} ${-Math.max(6,r+1)} ${Math.max(12,2*r+2)} ${Math.max(12,2*r+2)}" style="margin-right:5px;vertical-align:-1px"><path d="${mark(k==='diamond'||k==='square'?k:'dot',0,0,r)}" ${Object.entries(markStyle(k==='hollow',k==='regional'?'#aaa':col,k==='books',k==='regional',col)).map(([a,v])=>`${a}="${v}"`).join(' ')}/></svg>`;
export function legend(items){return '<div class="legend">'+items.map(([c,t,d])=>`<span><i style="background:${c}${d?';background-image:repeating-linear-gradient(90deg,transparent 0 3px,#fff 3px 5px)':''}"></i>${esc(t)}</span>`).join('')+'</div>'}
export const METHODS=`<p>Births come from the US Social Security Administration, the ONS (England and Wales), New South Wales and Ontario. Names under a publishing threshold are absent from those files, so a missing value means unknown or very small, never zero.</p>
<p>Attention is median monthly English Wikipedia views over the last 12 months, with page moves merged, for the brand's page and the original meaning's page. People look up companies more than fruit, so this over-counts brands. It is one signal, along with capitalization in Google Books through 2022. The small graphs beside dictionary entries show uses in Google Books.</p>
<p>Marker sizes show monthly brand Wikipedia views on a log scale, relative to the brands shown. All markers are circles, coloured by group. A thin dark outline marks brands known only in one region. Solid fills show Wikipedia traffic. Paler, more transparent fills show estimates when there is no usable Wikipedia comparison: only a positive rise in capitalization in books since before the launch yields an estimate, and books lag behind speech, so recent brands are understated. A hollow marker marks a discontinued product, which can still own the word. Regional products keep their dark outline when hollow.</p>
<p>A word counts if it now also names a product, service, company or franchise, and the general public uses the bare word for it. Company-owned characters count. Bands and people do not, which is an editorial choice. Words where both sides together get under 300 views a month are left out as too thin to judge.</p>
<p>The groups are editorial judgments informed by that data, not outputs of a formula. A fall in a name after a launch does not prove the launch caused it, which is why similar names sit beside it where they exist.</p>
<p>A trademark covers specific goods and services. It does not own a word. Registration details per entry are being added.</p>`;
