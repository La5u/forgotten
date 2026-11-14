import {GROUPS,legend,esc,num,pct,lineChart} from './shared.js';
const groups=Object.keys(GROUPS).filter(g=>g!=='watching'),ordinary=e=>['common','rare'].includes(e.kind)&&e.word===e.word.toLowerCase(),pc=v=>(v*100).toFixed(1)+'%',pp=v=>pct(+(v*100).toFixed(1)).replace('%',''),NS='http://www.w3.org/2000/svg';
const el=(tag,a={},p,text)=>{const n=document.createElementNS(NS,tag);for(const k in a)n.setAttribute(k,a[k]);if(text!=null)n.textContent=text;p?.append(n);return n};
let tip;
const hide=()=>{if(tip)tip.style.display='none'};
function show(html,node,event){if(!tip){tip=document.createElement('div');tip.className='tip';tip.setAttribute('role','status');document.body.append(tip)}tip.innerHTML=html;tip.style.display='block';const r=node.getBoundingClientRect(),x=event?.clientX??r.left,y=event?.clientY??r.top;tip.style.left=Math.max(6,Math.min(innerWidth-tip.offsetWidth-6,x+12))+'px';tip.style.top=Math.max(6,Math.min(innerHeight-tip.offsetHeight-6,y-tip.offsetHeight-12))+'px'}
function bind(n,html){n.setAttribute('tabindex',0);n.setAttribute('role','button');n.setAttribute('aria-label',html.replace(/<[^>]*>/g,' '));const on=e=>show(html,n,e);n.addEventListener('pointermove',on);n.addEventListener('click',on);n.addEventListener('focus',()=>show(html,n));n.addEventListener('pointerleave',hide);n.addEventListener('blur',hide);n.addEventListener('keydown',e=>{if(e.key==='Escape')hide();if(e.key==='Enter'||e.key===' '){e.preventDefault();show(html,n)}})}
function setup(section,gs=groups){section.querySelector('.chart-legend').innerHTML=legend(gs.map(g=>[GROUPS[g].color,GROUPS[g].label]));return section.querySelector('.chart')}
function svg(host,H,label){hide();host.innerHTML='';const W=Math.max(280,host.clientWidth||700),s=el('svg',{viewBox:`0 0 ${W} ${H}`,role:'group','aria-label':label},host);return {s,W,H}}
function grid(s,x1,x2,y,label){el('line',{x1,x2,y1:y,y2:y,stroke:'#0000001a'},s);el('text',{x:x1-7,y:y+4,'text-anchor':'end'},s,label)}
const quantile=(a,p)=>{const i=(a.length-1)*p,j=Math.floor(i);return a[j]+(a[Math.ceil(i)]-a[j])*(i-j)};
export function curveData(entries,sparks){
  const rows=entries.filter(e=>ordinary(e)&&groups.includes(e.group)).map(e=>{const a=sparks.entries[e.word];if(!a?.[0]||!a[1])return null;const lo=a[0].map(v=>v*10**a[2]),cap=a[1].map(v=>v*10**a[3]);
    const at=y=>{const t=(y-sparks.from-1)/sparks.step;if(t<0||t>lo.length-1)return null;const i=Math.floor(t),j=Math.ceil(t),f=t-i,l=lo[i]*(1-f)+lo[j]*f,c=cap[i]*(1-f)+cap[j]*f;return l+c>0?c/(l+c):null};return {e,at}}).filter(Boolean);
  return groups.map(g=>({g,points:Array.from({length:24},(_,i)=>-30+i*3).map(x=>{const a=rows.filter(r=>r.e.group===g).map(r=>r.at(r.e.launch_year+x)).filter(v=>v!=null).sort((a,b)=>a-b);return {x,n:a.length,...(a.length>=15?{q1:quantile(a,.25),mid:quantile(a,.5),q3:quantile(a,.75)}:{})}})}))}
export function takeoverCurve(section,entries,sparks){const host=setup(section,groups);let selected='';const series=curveData(entries,sparks);
  const draw=()=>{const {s,W,H}=svg(host,350,'Capitalisation by years since brand launch'),m={l:48,r:14,t:26,b:44},X=x=>m.l+(x+30)/69*(W-m.l-m.r),Y=v=>H-m.b-v*(H-m.t-m.b);
    for(const v of [0,.25,.5,.75,1])grid(s,m.l,W-m.r,Y(v),Math.round(v*100)+'%');
    for(const x of[-30,-15,0,15,30,39])el('text',{x:X(x),y:H-24,'text-anchor':'middle'},s,x===0?'Launch':x>0?'+'+x:x);
    el('text',{x:m.l,y:13},s,'↑ Capitalised share');el('text',{x:(W+m.l-m.r)/2,y:H-4,'text-anchor':'middle'},s,'Years since launch');el('line',{x1:X(0),x2:X(0),y1:m.t,y2:H-m.b,stroke:'#111', 'stroke-dasharray':'3 4',opacity:.4},s);
    for(const {g,points} of series){const layer=el('g',{'data-group':g},s),color=GROUPS[g].color;let runs=[],run=[];for(const p of points){if(p.mid==null){if(run.length)runs.push(run);run=[]}else run.push(p)}if(run.length)runs.push(run);
      for(const r of runs){el('path',{d:r.map((p,i)=>(i?'L':'M')+X(p.x)+' '+Y(p.q1)).join('')+[...r].reverse().map(p=>'L'+X(p.x)+' '+Y(p.q3)).join('')+'Z',fill:color,opacity:.12},layer);el('path',{d:r.map((p,i)=>(i?'L':'M')+X(p.x)+' '+Y(p.mid)).join(''),fill:'none',stroke:color,'stroke-width':2.5},layer);
        for(const p of r){const n=el('circle',{cx:X(p.x),cy:Y(p.mid),r:9,fill:'transparent'},layer);bind(n,`<b>${GROUPS[g].label}</b> · ${p.x===0?'launch':p.x+' years'}<div>Median ${pc(p.mid)}</div><div>Middle half: ${pc(p.q1)} to ${pc(p.q3)}</div><div>${num(p.n)} words</div>`)}}
    }
    const focus=g=>s.querySelectorAll('[data-group]').forEach(n=>n.setAttribute('opacity',!g||n.dataset.group===g?1:.15));focus(selected);
    section.querySelectorAll('.chart-legend span').forEach((n,i)=>{n.tabIndex=0;n.setAttribute('role','button');n.setAttribute('aria-label','Highlight '+GROUPS[groups[i]].label);n.onpointerenter=()=>focus(groups[i]);n.onpointerleave=()=>focus(selected);n.onfocus=()=>focus(groups[i]);n.onblur=()=>focus(selected);n.onclick=()=>{selected=selected===groups[i]?'':groups[i];focus(selected)};n.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();n.click()}}});
  };section.querySelector('.note').textContent='Lowercase words only, with at least 15 words per point and no estimates outside 1901–2021. The words counted change along each line, and capitals can also be sentence starts or other names.';draw();addEventListener('resize',draw)}
export function dumbbellData(entries){return entries.filter(e=>ordinary(e)&&e.cap_pre!=null&&e.cap_2022!=null&&e.brand_views>=20000&&e.pre_launch_per_million>=.01).sort((a,b)=>(b.cap_2022-b.cap_pre)-(a.cap_2022-a.cap_pre)||a.word.localeCompare(b.word)).slice(0,30)}
export function capitalisationDumbbells(section,entries){const data=dumbbellData(entries),host=setup(section,[...new Set(data.map(e=>e.group))]);const draw=()=>{const {s,W,H}=svg(host,850,'Thirty largest rises in capitalisation'),l=W<500?83:115,r=44,t=38,b=32,X=v=>l+v*(W-l-r),row=(H-t-b)/30;
    for(const v of[0,.25,.5,.75,1]){el('line',{x1:X(v),x2:X(v),y1:t-10,y2:H-b,stroke:'#0000001a'},s);el('text',{x:X(v),y:17,'text-anchor':'middle'},s,Math.round(v*100)+'%')}
    data.forEach((e,i)=>{const y=t+(i+.5)*row,c=GROUPS[e.group].color;el('text',{x:l-9,y:y+4,'text-anchor':'end',fill:'#111'},s,e.word);el('line',{x1:X(e.cap_pre),x2:X(e.cap_2022),y1:y,y2:y,stroke:c,'stroke-width':2},s);for(const [v,open] of[[e.cap_pre,true],[e.cap_2022,false]])el('circle',{cx:X(v),cy:y,r:4,fill:open?'#fff':c,stroke:c,'stroke-width':1.5},s);el('text',{x:W-2,y:y+4,'text-anchor':'end'},s,pp(e.cap_2022-e.cap_pre));const n=el('rect',{x:0,y:y-row/2,width:W,height:row,fill:'transparent'},s);bind(n,`<b>${esc(e.word)}</b> · ${GROUPS[e.group].label}<div>${pc(e.cap_pre)} before launch → ${pc(e.cap_2022)} in 2022</div><div>Rise: ${pp(e.cap_2022-e.cap_pre)} points</div><div>Before launch: ${e.pre_launch_per_million} uses per million</div><div>${num(e.brand_views)} monthly brand views</div>`)});el('text',{x:l,y:H-5},s,'Capitalised share →');
  };section.querySelector('.note').textContent='Words need at least 0.01 uses per million before launch; numbers on the right show the rise in percentage points. Capitals can refer to other names too; hover or tap a row for details.';draw();addEventListener('resize',draw)}

const types=['company','character'],labels={company:'Companies',character:'Characters'},colors={company:GROUPS.taken.color,character:GROUPS.failed.color};
const round=v=>Math.round(v*10)/10;
const pm=(x,y)=>{const r=x.series.us,i=y-r.from;return y<1880||y>2025?null:(r.per_million[i]??0)},base=x=>[-3,-2,-1].reduce((s,k)=>s+pm(x,x.launch_year+k),0)/3;
// Match build_names.py: use stored changes where available and round median changes with ties to even.
const medianChange=a=>{const v=quantile(a,.5),lo=Math.floor(v);return v-lo===.5?lo+Math.abs(lo%2):Math.round(v)};
export function aligned(names){return types.map(type=>({type,rows:Array.from({length:26},(_,i)=>{const x=i-10,a=names.filter(n=>n.type===type&&n.stats).map(n=>{if(x in n.stats.after)return n.stats.after[x];const v=pm(n,n.launch_year+x);return v==null?null:100*(v/base(n)-1)}).filter(v=>v!=null).sort((a,b)=>a-b);
  return {x,n:a.length,...(a.length>=10?{lo:100+quantile(a,.25),mid:100+medianChange(a),hi:100+quantile(a,.75)}:{})}})}))}
function aggregate(host,groups){host.innerHTML='';const W=Math.max(280,host.clientWidth||700),H=350,m={l:44,r:12,t:25,b:44},pw=W-m.l-m.r,ph=H-m.t-m.b,max=Math.ceil(Math.max(...groups.flatMap(g=>g.rows.map(r=>r.hi||0)))/100)*100,X=x=>m.l+(x+10)/25*pw,Y=y=>H-m.b-y/max*ph;
  const svg=el('svg',{viewBox:`0 0 ${W} ${H}`,width:'100%',role:'group','aria-label':'Median name popularity around launch, with middle-half bands'},host);
  el('text',{x:m.l,y:12,'font-size':11,fill:'#666'},svg,'Before launch = 100');
  for(let v=0;v<=max;v+=max/4){el('line',{x1:m.l,x2:W-m.r,y1:Y(v),y2:Y(v),stroke:'#0000001a'},svg);el('text',{x:m.l-6,y:Y(v)+4,'text-anchor':'end','font-size':11,fill:'#666'},svg,num(v))}
  el('line',{x1:m.l,x2:W-m.r,y1:Y(100),y2:Y(100),stroke:'#111',opacity:.5,'stroke-dasharray':'3 3'},svg);
  el('line',{x1:X(0),x2:X(0),y1:m.t,y2:H-m.b,stroke:'#111','stroke-dasharray':'2 3'},svg);el('text',{x:X(0)+4,y:12,'font-size':11},svg,'Launch');
  for(let x=-10;x<=15;x+=5)el('text',{x:X(x),y:H-m.b+18,'text-anchor':'middle','font-size':11,fill:'#666'},svg,x>0?'+'+x:x);
  el('text',{x:(W+m.l-m.r)/2,y:H-4,'text-anchor':'middle','font-size':11,fill:'#666'},svg,'Years since launch');
  const path=(rows,key,y)=>{let on=false;return rows.map(r=>{if(r.mid==null){on=false;return ''}const s=(on?'L':'M')+X(r.x)+' '+y(r[key]);on=true;return s}).join('')};
  for(const g of groups){const c=colors[g.type];let runs=[],run=[];for(const r of g.rows){if(r.mid!=null)run.push(r);else if(run.length){runs.push(run);run=[]}}if(run.length)runs.push(run);
    for(const r of runs)el('path',{d:path(r,'hi',Y)+[...r].reverse().map(v=>'L'+X(v.x)+' '+Y(v.lo)).join('')+'Z',fill:c,opacity:.12},svg);
    el('path',{d:path(g.rows,'mid',Y),fill:'none',stroke:c,'stroke-width':2.5},svg)}
  const cross=el('line',{y1:m.t,y2:H-m.b,stroke:'#111',opacity:0},svg),tip=document.createElement('div');tip.className='tip';host.append(tip);
  const hit=el('rect',{x:m.l,y:m.t,width:pw,height:ph,fill:'transparent',tabindex:0,role:'slider','aria-label':'Years from launch','aria-valuemin':-10,'aria-valuemax':15,'aria-valuenow':0},svg);let cur=0;
  const show=x=>{cur=x;cross.setAttribute('x1',X(x));cross.setAttribute('x2',X(x));cross.setAttribute('opacity',.3);const rows=groups.map(g=>{const r=g.rows[x+10];return `${labels[g.type]}: ${r.mid==null?'under 10 names':`${round(r.mid)} (middle half ${round(r.lo)} to ${round(r.hi)})`}; ${r.n} names`});
    hit.setAttribute('aria-valuenow',x);hit.setAttribute('aria-valuetext',`${x} years from launch. ${rows.join('. ')}`);tip.innerHTML=`<b>${x===0?'Launch year':Math.abs(x)+' years '+(x<0?'before':'after')+' launch'}</b>`+rows.map(s=>'<div>'+esc(s)+'</div>').join('');tip.style.display='block';const r=svg.getBoundingClientRect();tip.style.left=Math.max(6,Math.min(innerWidth-tip.offsetWidth-6,r.left+X(x)*r.width/W+10))+'px';tip.style.top=Math.max(6,r.top+30)+'px'};
  const hide=()=>{tip.style.display='none';cross.setAttribute('opacity',0)},at=e=>{const r=svg.getBoundingClientRect();show(Math.max(-10,Math.min(15,Math.round(((e.clientX-r.left)*W/r.width-m.l)/pw*25-10))))};
  hit.addEventListener('pointermove',at);hit.addEventListener('pointerdown',at);hit.addEventListener('pointerleave',hide);hit.addEventListener('blur',hide);hit.addEventListener('focus',()=>show(cur));hit.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();show(Math.max(-10,Math.min(15,cur+(e.key==='ArrowLeft'?-1:1))))}})
}
export async function pageCharts(entries){const [S,N,C]=await Promise.all(['sparks.json','names.json','name_controls.json'].map(async f=>{const r=await fetch(new URL(f,import.meta.url));if(!r.ok)throw Error(f+': '+r.status);return r.json()})), $=s=>document.querySelector(s),groups=aligned(N.names),row=t=>groups.find(g=>g.type===t).rows[15];
  takeoverCurve($('#takeover'),entries,S);capitalisationDumbbells($('#dumbbells'),entries);
  $('#aggregate-legend').innerHTML=legend(types.map(t=>[colors[t],labels[t]]));
  $('#aggregate-finding').textContent='No general penalty: the middle name barely moves after a launch, for companies and characters alike. Alexa and Siri are exceptions.';
  $('#aggregate-note').textContent=`US births per million, with each name set to 100 at its average in the three years before launch; lines show medians rounded to whole points and bands the middle half. All outcomes among site names count, with at least 20 births a year before launch: ${row('company').n} company names and ${row('character').n} character names at year five. Counts vary by year; points with fewer than 10 names are left out. Hover, tap or use arrow keys for values.`;
  const points=a=>Object.fromEntries(a.map((v,i)=>[C.from+i,v])),a=C.series.Alexa,A=points(a.map(v=>v==null?null:100*v/a[C.base_year-C.from])),P=points(C.peers_index),comparison=`Other girls' names popular in the 2000s (median of ${C.peers.length})`,series=[{name:'Alexa',color:colors.company,points:A},{name:comparison,color:colors.character,points:P}],fall=p=>(100*(1-p[2025]/p[2015])).toFixed(1);
  $('#alexa-finding').textContent=`From 2015 to 2025, Alexa fell ${fall(A)}% in US births per million, while the comparison names fell ${fall(P)}%.`;
  $('#l1').innerHTML=legend(series.map(s=>[s.color,s.name]));$('#comparison-names').textContent=C.peers.join(', ')+'.';
  const draw=()=>{aggregate($('#aggregate'),groups);lineChart($('#f1'),{from:C.from,to:C.to,height:340,endLabels:false,right:14,mark:{year:2014.9,label:'Echo, late 2014'},ink:'#16130f',series:series.map(s=>({...s,fmt:y=>`${round(s.points[y])} (2014 = 100)`}))})};
  $('#f1').addEventListener('pointerdown',e=>{if(e.target.matches('svg rect'))e.target.dispatchEvent(new PointerEvent('pointermove',{clientX:e.clientX,clientY:e.clientY,bubbles:true}))});
  draw();let timer;addEventListener('resize',()=>{clearTimeout(timer);timer=setTimeout(draw,120)})
}
