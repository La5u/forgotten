import {legend,esc,num,lineChart,headerOffset} from './shared.js';
import {nameStrip} from './parts.js';
const NS='http://www.w3.org/2000/svg',quantile=(a,p)=>{const i=(a.length-1)*p,j=Math.floor(i);return a[j]+(a[Math.ceil(i)]-a[j])*(i-j)};
const el=(tag,a={},p,text)=>{const n=document.createElementNS(NS,tag);for(const k in a)n.setAttribute(k,a[k]);if(text!=null)n.textContent=text;p?.append(n);return n};
const types=['company','character'],labels={company:'Products',character:'Fictional characters'},colors={company:'#1768a4',character:'#454545'};
const round=v=>Math.round(v*10)/10;
const pm=(x,y)=>{const r=x.series.us,i=y-r.from;return y<1880||y>2025?null:(r.per_million[i]??0)},base=x=>[-3,-2,-1].reduce((s,k)=>s+pm(x,x.launch_year+k),0)/3;
// Match build_names.py: use stored changes where available and round median changes with ties to even.
const medianChange=a=>{const v=quantile(a,.5),lo=Math.floor(v);return v-lo===.5?lo+Math.abs(lo%2):Math.round(v)};
export function aligned(names){return types.map(type=>({type,rows:Array.from({length:26},(_,i)=>{const x=i-10,a=names.filter(n=>n.type===type&&n.stats).map(n=>{if(x in n.stats.after)return n.stats.after[x];const v=pm(n,n.launch_year+x);return v==null?null:100*(v/base(n)-1)}).filter(v=>v!=null).sort((a,b)=>a-b);
  return {x,n:a.length,...(a.length>=10?{lo:100+quantile(a,.25),mid:100+medianChange(a),hi:100+quantile(a,.75)}:{})}})}))}
function aggregate(host,groups){host.innerHTML='';const W=Math.max(280,host.clientWidth||700),H=350,m={l:44,r:12,t:25,b:44},pw=W-m.l-m.r,ph=H-m.t-m.b,max=200,X=x=>m.l+(x+10)/25*pw,Y=y=>H-m.b-y/max*ph;
  const svg=el('svg',{viewBox:`0 0 ${W} ${H}`,width:'100%',role:'group','aria-label':'Median name popularity around launch, with middle-half bands'},host);
  el('text',{x:m.l,y:12,'font-size':11,fill:'#666'},svg,'Before launch = 100');
  for(let v=0;v<=max;v+=max/4){el('line',{x1:m.l,x2:W-m.r,y1:Y(v),y2:Y(v),stroke:'#0000001a'},svg);el('text',{x:m.l-6,y:Y(v)+4,'text-anchor':'end','font-size':11,fill:'#666'},svg,num(v))}
  el('line',{x1:m.l,x2:W-m.r,y1:Y(100),y2:Y(100),stroke:'#111',opacity:.5,'stroke-dasharray':'3 3'},svg);
  el('line',{x1:X(0),x2:X(0),y1:m.t,y2:H-m.b,stroke:'#111','stroke-dasharray':'2 3'},svg);el('text',{x:X(0)+4,y:12,'font-size':11},svg,'Launch');
  for(let x=-10;x<=15;x+=5)el('text',{x:X(x),y:H-m.b+18,'text-anchor':'middle','font-size':11,fill:'#666'},svg,x>0?'+'+x:x);
  el('text',{x:(W+m.l-m.r)/2,y:H-4,'text-anchor':'middle','font-size':11,fill:'#666'},svg,'Years since launch');
  const path=(rows,key,y)=>{let on=false;return rows.map(r=>{if(r.mid==null){on=false;return ''}const s=(on?'L':'M')+X(r.x)+' '+y(r[key]);on=true;return s}).join('')};
  const clip=el('clipPath',{id:'aggregate-clip'},el('defs',{},svg));el('rect',{x:m.l,y:m.t,width:pw,height:ph},clip);const layer=el('g',{'clip-path':'url(#aggregate-clip)'},svg);
  for(const g of groups){const c=colors[g.type];let runs=[],run=[];for(const r of g.rows){if(r.mid!=null)run.push(r);else if(run.length){runs.push(run);run=[]}}if(run.length)runs.push(run);
    for(const r of runs)el('path',{d:path(r,'hi',Y)+[...r].reverse().map(v=>'L'+X(v.x)+' '+Y(v.lo)).join('')+'Z',fill:c,'fill-opacity':.10},layer);
    el('path',{d:path(g.rows,'mid',Y),fill:'none',stroke:c,'stroke-width':2.5},layer)}
  const cross=el('line',{y1:m.t,y2:H-m.b,stroke:'#111',opacity:0},svg),tip=document.createElement('div');tip.className='tip';host.append(tip);
  const hit=el('rect',{x:m.l,y:m.t,width:pw,height:ph,fill:'transparent',tabindex:0,role:'slider','aria-label':'Years from launch','aria-valuemin':-10,'aria-valuemax':15,'aria-valuenow':0},svg);let cur=0;
  const show=x=>{cur=x;cross.setAttribute('x1',X(x));cross.setAttribute('x2',X(x));cross.setAttribute('opacity',.3);const rows=groups.map(g=>{const r=g.rows[x+10];return `${labels[g.type]}: ${r.mid==null?'under 10 names':`${round(r.mid)} (middle half ${round(r.lo)} to ${round(r.hi)})`}; ${r.n} names`});
    hit.setAttribute('aria-valuenow',x);hit.setAttribute('aria-valuetext',`${x} years from launch. ${rows.join('. ')}`);tip.innerHTML=`<b>${x===0?'Launch year':Math.abs(x)+' years '+(x<0?'before':'after')+' launch'}</b>`+rows.map(s=>'<div>'+esc(s)+'</div>').join('');tip.style.display='block';const r=svg.getBoundingClientRect();tip.style.left=Math.max(6,Math.min(innerWidth-tip.offsetWidth-6,r.left+X(x)*r.width/W+10))+'px';tip.style.top=Math.max(6,r.top+30)+'px'};
  const hide=()=>{tip.style.display='none';cross.setAttribute('opacity',0)},at=e=>{const r=svg.getBoundingClientRect();show(Math.max(-10,Math.min(15,Math.round(((e.clientX-r.left)*W/r.width-m.l)/pw*25-10))))};
  hit.addEventListener('pointermove',at);hit.addEventListener('pointerdown',at);hit.addEventListener('pointerleave',hide);hit.addEventListener('blur',hide);hit.addEventListener('focus',()=>show(cur));hit.addEventListener('keydown',e=>{if(['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();show(Math.max(-10,Math.min(15,cur+(e.key==='ArrowLeft'?-1:1))))}})
}
export function nameCarousel(section,C,key){const $=s=>section.querySelector(s),rows=(C[key]||[]).map(name=>C.names.find(n=>n.name===name)).filter(Boolean);let index=0;
  section.hidden=!rows.length;if(!rows.length)return;
  for(const selector of ['.carousel-prev','.carousel-next'])$(selector).hidden=rows.length<2;
  section.querySelector(':scope > p:last-child').hidden=rows.length<2;
  const points=(a,from)=>Object.fromEntries(a.map((v,i)=>[from+i,v])),jumpHost=$('.carousel-names');
  jumpHost.innerHTML=rows.map((n,i)=>`<button type="button" data-index="${i}" aria-pressed="${i===0}">${esc(n.name)}</button>`).join('');
  jumpHost.hidden=rows.length<2;
  const draw=()=>{const n=rows[index],A=points(n.name_index,n.from),P=points(n.comparison_index,n.from),comparison=`Other ${n.sex==='F'?"girls'":n.sex==='M'?"boys'":''} names popular at the same time (median of ${n.peers.length})`;
    $('.carousel-chart rect[fill="transparent"]')?.dispatchEvent(new Event('pointerleave'));
    $('.carousel-title').textContent=`${n.name}, after ${n.brand}`;$('.carousel-type').textContent=n.type==='company'?'Product':n.type==='character'?'Fictional character':'Name';
    $('.carousel-position').textContent=`${index+1} of ${rows.length}`;
    jumpHost.querySelectorAll('button').forEach((button,i)=>button.setAttribute('aria-pressed',i===index));
    const after=n.after_years===6?'six years':`${n.after_years} available years`,long=n.test==='long',change=100*(long?n.end_ratio/n.before-1:n.change);
    $('.carousel-finding').textContent=n.test==='spike'?`In ${n.launch} to ${n.launch+2}, ${n.name} peaked ${Math.round(100*(n.early_peak/n.before-1))}% above its earlier level and averaged ${Math.round(Math.abs(100*n.change))}% ${n.change<0?'below':'above'} that level in the ${after} after launch, measured against names popular at the same time.`:long?`By ${n.end_to}, ${n.name} stood ${Math.round(Math.abs(change))}% ${change<0?'below':'above'} its level in the six years before launch, measured against names popular at the same time.`:`In the ${after} after launch, ${n.name} averaged ${Math.round(Math.abs(change))}% ${change<0?'below':'above'} its level in the six years before, measured against names popular at the same time.`;
    $('.carousel-five').textContent=`Six years before against ${after} after; a bigger change than ${Math.round(n.placebo_percentile)}% of names popular at the same time.`;
    $('.comparison-names').textContent=n.peers.join(', ')+'.';
    $('.carousel-legend').innerHTML=[['#16130f',n.name,2.6],['#888',comparison,1.4]].map(([c,label,w])=>`<span><svg width="20" height="12" aria-hidden="true"><path d="M0 6H20" stroke="${c}" stroke-width="${w}"/></svg> ${esc(label)}</span>`).join('');
    const series=[{name:comparison,color:'#888',points:P},{name:n.name,color:'#16130f',points:A}],s=lineChart($('.carousel-chart'),{from:n.from,to:n.end,height:340,endLabels:false,right:14,tab:rows.length<2,mark:{year:n.launch,label:`Launch, ${n.launch}`},ink:'#16130f',series:series.map(s=>({...s,fmt:y=>Math.round(s.points[y])+' (100 is the average before launch)'}))});
    s.querySelectorAll('path').forEach((p,i)=>p.setAttribute('stroke-width',i?2.6:1.4));s.querySelectorAll('circle').forEach((p,i)=>p.setAttribute('r',i?3.5:2.5));
    s.setAttribute('aria-label',`${n.name} and comparison names, ${n.from} to ${n.end}. Set to 100 at the average in the three years before launch. ${$('.carousel-finding').textContent} ${$('.carousel-five').textContent}`);
  };
  jumpHost.onclick=e=>{const button=e.target.closest('button[data-index]');if(button){index=Number(button.dataset.index);draw()}};
  const step=d=>{index=(index+d+rows.length)%rows.length;draw()};$('.carousel-prev').onclick=()=>step(-1);$('.carousel-next').onclick=()=>step(1);
  section.addEventListener('keydown',e=>{if(rows.length>1&&!e.altKey&&!e.ctrlKey&&!e.metaKey&&['ArrowLeft','ArrowRight'].includes(e.key)){e.preventDefault();step(e.key==='ArrowLeft'?-1:1)}});
  let start;const host=$('.carousel-chart');host.style.touchAction='pan-y';host.addEventListener('pointerdown',e=>{if(rows.length>1&&e.pointerType==='touch')start={x:e.clientX,y:e.clientY}});host.addEventListener('pointercancel',()=>start=null);host.addEventListener('pointerup',e=>{if(!start)return;const dx=e.clientX-start.x,dy=e.clientY-start.y;start=null;if(Math.abs(dx)>45&&Math.abs(dx)>Math.abs(dy)*1.5)step(dx<0?1:-1)});
  host.addEventListener('pointerdown',e=>{if(e.target.matches('svg rect'))e.target.dispatchEvent(new PointerEvent('pointermove',{clientX:e.clientX,clientY:e.clientY,bubbles:true}))});
  draw();let timer;addEventListener('resize',()=>{clearTimeout(timer);timer=setTimeout(draw,120)})
}

async function namesCharts(){const [N,C]=await Promise.all(['names.json','name_controls.json'].map(async f=>{const r=await fetch(new URL(f,import.meta.url));if(!r.ok)throw Error(f+': '+r.status);return r.json()})), $=s=>document.querySelector(s),groups=aligned(N.names),row=t=>groups.find(g=>g.type===t).rows[15];
  $('#aggregate-legend').innerHTML=legend(types.map(t=>[colors[t],labels[t]]));
  $('#aggregate-finding').textContent='No general penalty: the middle name barely moves after a launch, for products and fictional characters alike. Alexa and Siri are exceptions.';
  $('#aggregate-method').textContent=`US births per million (SSA), with each name set to 100 at its average in the three years before launch; lines show medians rounded to whole points and bands the middle half. All outcomes among site names count, with at least 20 births a year before launch: ${row('company').n} product names and ${row('character').n} fictional character names at year five. Counts vary by year; points with fewer than 10 names are left out. The axis stops at 200 and clips the bands. Hover, tap or use arrow keys for values.`;
  nameCarousel($('#alexa'),C,'worst');nameCarousel($('#name-lift'),C,'lift');nameCarousel($('#name-spike'),C,'spike');
  nameStrip($('#names'),N);
  const draw=()=>aggregate($('#aggregate'),groups);draw();let timer;addEventListener('resize',()=>{clearTimeout(timer);timer=setTimeout(draw,120)})
}

headerOffset();
namesCharts().catch(console.error);
