// Dictionary book histories. One fetch, one observer; only nearby entries get SVGs.
import {GROUPS,esc} from './shared.js';
// Require a crossing, then at least two bins above lowercase through the end.
export function lastingCrossover(pair,launch,{from,step}){const [lo,hi]=pair;if(!lo||!hi||launch==null||launch<1900||lo.length!==hi.length)return null;
  for(let i=1;i<lo.length-1;i++){const a=hi[i-1]-lo[i-1],b=hi[i]-lo[i];if(a>0||b<=0||!hi.slice(i).every((v,j)=>v>lo[i+j]))continue;
    let j=i-1;while(j>=0&&hi[j]===lo[j])j--;if(j<0||hi[j]>lo[j])continue;
    const t=-a/(b-a),year=from+1+(i-1+t)*step;if(year>launch)return {year,value:hi[i-1]+t*(hi[i]-hi[i-1])}}
  return null}
export function dictionarySparks(data,{crossovers=false}={}){let D,rows=[],io;
  const draw=(host,e)=>{const data=D.entries[e.word],pair=data.slice(0,2).map((s,j)=>s?.map(v=>v*10**data[j+2])),both=pair.every(Boolean),max=Math.max(...pair.flatMap(s=>s||[]))||1,
      X=y=>2+(y-D.from)/(D.to-D.from)*146,Y=v=>30-v/max*28,
      lines=pair.map((s,j)=>s?`<path d="${s.map((v,i)=>(i?'L':'M')+X(D.from+1+i*D.step).toFixed(1)+' '+Y(v).toFixed(1)).join('')}" fill="none" stroke="${both&&j?GROUPS[e.group].color:'currentColor'}" stroke-width="${both&&j?1:1.5}" opacity="${both&&j? .7:1}"/>`:'').join(''),
      launch=e.launch_year>=D.from&&e.launch_year<=D.to,cross=crossovers?lastingCrossover(pair,e.launch_year,D):null,
      title=`Printed uses per million words in books, ${D.from}-${D.to}: ${both?'lowercase vs Capitalized':pair[0]?'lowercase':'Capitalized'}; three-year averages${launch?`; line marks the launch (${e.launch_year})`:''}${cross?`; dot: Capitalized stays above lowercase from about ${Math.round(cross.year)}`:''}`;
    host.innerHTML=`<svg class="sparkline" width="150" height="44" viewBox="0 0 150 44" role="img" aria-label="${esc(title)}" ${cross?'tabindex="0"':''}><title>${esc(title)}</title>${launch?`<line x1="${X(e.launch_year).toFixed(1)}" x2="${X(e.launch_year).toFixed(1)}" y1="1" y2="31" stroke="currentColor" stroke-width=".6" stroke-dasharray="2 2" opacity=".5"/>`:''}${lines}${cross?`<circle cx="${X(cross.year).toFixed(1)}" cy="${Y(cross.value).toFixed(1)}" r="2.2" fill="${GROUPS[e.group].color}" stroke="var(--p, #fff)" stroke-width=".7"/>`:''}<g fill="var(--s)" font-size="8" font-family="var(--sans)"><text x="2" y="42">${D.from}</text><text x="148" y="42" text-anchor="end">${D.to}</text></g></svg>`;
    if(cross){host.title=title;host.onclick=()=>{let note=host.querySelector('.note');if(!note){note=document.createElement('span');note.className='note';note.textContent=`Capitalized stays above lowercase from about ${Math.round(cross.year)}.`;host.append(note)}else note.hidden=!note.hidden};host.onkeydown=ev=>{if(ev.key==='Enter'||ev.key===' '){ev.preventDefault();host.onclick()}}}};
  const watch=()=>{io?.disconnect();if(!D)return;
    const pending=new Map();
    io=new IntersectionObserver(es=>{for(const x of es)if(x.isIntersecting){const e=pending.get(x.target);if(e&&x.target.isConnected)draw(x.target,e);pending.delete(x.target);io.unobserve(x.target)}},{rootMargin:'400px 0px'});
    for(const [node,e] of rows){if(!D.entries[e.word])continue;node.classList.add('has-spark');
      const host=document.createElement('div');host.className='spark';node.append(host);pending.set(host,e);io.observe(host)}};
  const ready=Promise.resolve(data).then(d=>{D=d;watch()}).catch(e=>console.warn('Book histories unavailable',e));  // data: promise of sparks.json
  return Object.assign((nodes,entries)=>{rows=Array.from(nodes,(node,i)=>[node,entries[i]]);watch()},{ready})}
