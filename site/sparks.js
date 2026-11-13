// Dictionary book histories. One fetch, one observer; only nearby entries get SVGs.
import {GROUPS,esc} from './shared.js';
export function dictionarySparks(url){let D,rows=[],io;
  const draw=(host,e)=>{const data=D.entries[e.word],pair=data.slice(0,2).map((s,j)=>s?.map(v=>v*10**data[j+2])),both=pair.every(Boolean),max=Math.max(...pair.flatMap(s=>s||[]))||1,
      X=y=>2+(y-D.from)/(D.to-D.from)*146,Y=v=>30-v/max*28,
      lines=pair.map((s,j)=>s?`<path d="${s.map((v,i)=>(i?'L':'M')+X(D.from+1+i*D.step).toFixed(1)+' '+Y(v).toFixed(1)).join('')}" fill="none" stroke="${both&&j?GROUPS[e.group].color:'currentColor'}" stroke-width="${both&&j?1:1.5}" opacity="${both&&j? .7:1}"/>`:'').join(''),
      launch=e.launch_year>=D.from&&e.launch_year<=D.to,
      title=`Printed uses per million words in books, ${D.from}-${D.to}: ${both?'lowercase vs Capitalized':pair[0]?'lowercase':'Capitalized'}; three-year averages${launch?`; line marks the launch (${e.launch_year})`:''}`;
    host.innerHTML=`<svg class="sparkline" width="150" height="44" viewBox="0 0 150 44" role="img" aria-label="${esc(title)}"><title>${esc(title)}</title>${launch?`<line x1="${X(e.launch_year).toFixed(1)}" x2="${X(e.launch_year).toFixed(1)}" y1="1" y2="31" stroke="currentColor" stroke-width=".6" stroke-dasharray="2 2" opacity=".5"/>`:''}${lines}<g fill="var(--s)" font-size="8" font-family="var(--sans)"><text x="2" y="42">${D.from}</text><text x="148" y="42" text-anchor="end">${D.to}</text></g></svg>`};
  const watch=()=>{io?.disconnect();if(!D)return;
    const pending=new Map();
    io=new IntersectionObserver(es=>{for(const x of es)if(x.isIntersecting){const e=pending.get(x.target);if(e&&x.target.isConnected)draw(x.target,e);pending.delete(x.target);io.unobserve(x.target)}},{rootMargin:'400px 0px'});
    for(const [node,e] of rows){if(!D.entries[e.word])continue;node.classList.add('has-spark');
      const host=document.createElement('div');host.className='spark';node.append(host);pending.set(host,e);io.observe(host)}};
  // Let the initial dictionary paint before fetching or parsing the extra data.
  requestAnimationFrame(()=>setTimeout(async()=>{try{const r=await fetch(url);if(!r.ok)throw Error(r.status);D=await r.json();watch()}catch(e){console.warn('Book histories unavailable',e)}},0));
  return (nodes,entries)=>{rows=Array.from(nodes,(node,i)=>[node,entries[i]]);watch()}}
