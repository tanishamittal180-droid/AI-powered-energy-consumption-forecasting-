/* Dependency-free SVG charts: graphs render even when external CDNs are blocked. */
const $ = (id) => document.getElementById(id);
const fmt = (n, digits=1) => Number(n ?? 0).toLocaleString(undefined,{minimumFractionDigits:digits,maximumFractionDigits:digits});
const hideLoading = () => $("loading").classList.add("hidden");
const showLoading = () => $("loading").classList.remove("hidden");
let currentDashboard = null;
function toast(message, bad=false){const el=$("toast");el.textContent=message;el.style.background=bad?"#8b3e37":"#14383c";el.classList.add("show");clearTimeout(window.__toastTimer);window.__toastTimer=setTimeout(()=>el.classList.remove("show"),3800)}
function dateLabel(value){return new Date(value).toLocaleString([], {month:"short",day:"numeric",hour:"numeric"})}
function esc(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function svgLineChart(el, history, forecast){
 const hist=history.map(r=>({date:new Date(r.timestamp),value:Number(r.energy_kwh)})).filter(r=>Number.isFinite(r.value));
 const fut=forecast.map(r=>({date:new Date(r.timestamp),value:Number(r.predicted_kwh)})).filter(r=>Number.isFinite(r.value));
 if(!hist.length || !fut.length){el.innerHTML='<div class="chart-empty">Not enough data to draw the chart yet.</div>';return}
 const W=Math.max(320,el.clientWidth||700),H=Math.max(220,el.clientHeight||255),L=48,R=14,T=16,B=35,iw=W-L-R,ih=H-T-B;
 const vals=hist.concat(fut).map(d=>d.value),min=Math.min(...vals),max=Math.max(...vals),pad=Math.max((max-min)*.12,1),lo=Math.max(0,min-pad),hi=max+pad;
 const x=i=>L+(i/(hist.length+fut.length-1||1))*iw,y=v=>T+(hi-v)/(hi-lo||1)*ih;
 const histPts=hist.map((d,i)=>`${x(i).toFixed(1)},${y(d.value).toFixed(1)}`).join(' ');
 const forecastPts=[`${x(hist.length-1).toFixed(1)},${y(hist[hist.length-1].value).toFixed(1)}`,...fut.map((d,i)=>`${x(hist.length+i).toFixed(1)},${y(d.value).toFixed(1)}`)].join(' ');
 const yTicks=Array.from({length:5},(_,i)=>lo+(hi-lo)*i/4);
 const xIndices=[0,Math.floor((hist.length-1)/2),hist.length-1,hist.length+Math.floor((fut.length-1)/2),hist.length+fut.length-1].filter((v,i,a)=>a.indexOf(v)===i);
 let grid=yTicks.map(v=>`<line x1="${L}" y1="${y(v)}" x2="${W-R}" y2="${y(v)}" stroke="#edf2f3"/><text x="${L-9}" y="${y(v)+3}" text-anchor="end" fill="#94a5aa" font-size="10">${Math.round(v)}</text>`).join('');
 let xt=xIndices.map(i=>{let d=i<hist.length?hist[i].date:fut[Math.min(i-hist.length,fut.length-1)].date;return `<text x="${x(i)}" y="${H-11}" text-anchor="middle" fill="#91a2a7" font-size="9">${esc(dateLabel(d))}</text>`}).join('');
 const dots=fut.map((d,i)=>`<circle cx="${x(hist.length+i)}" cy="${y(d.value)}" r="2.5" fill="#20b486"><title>${esc(dateLabel(d.date))}: ${fmt(d.value,2)} kWh predicted</title></circle>`).join('');
 const area=`${L},${T+ih} ${histPts} ${x(hist.length-1)},${T+ih}`;
 el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" width="100%" height="100%" role="img" aria-label="Historical consumption and future energy forecast">${grid}<polygon points="${area}" fill="#b9cbd0" opacity=".13"/><polyline points="${histPts}" fill="none" stroke="#a9bdc2" stroke-width="2.2" stroke-linejoin="round" stroke-linecap="round"/><polyline points="${forecastPts}" fill="none" stroke="#22b58a" stroke-width="2.6" stroke-dasharray="6 5" stroke-linejoin="round" stroke-linecap="round"/>${dots}${xt}</svg>`;
}
function svgBarChart(el, labels, values, opts={}){
 const clean=values.map(v=>Number(v));if(!clean.length||clean.every(v=>!Number.isFinite(v))){el.innerHTML='<div class="chart-empty">No values available to plot.</div>';return}
 const W=Math.max(300,el.clientWidth||500),H=Math.max(160,el.clientHeight||185),L=38,R=8,T=12,B=31,iw=W-L-R,ih=H-T-B,max=Math.max(...clean.filter(Number.isFinite),1)*1.15;
 const slot=iw/clean.length,bw=Math.max(3,Math.min(26,slot*.62));
 const bars=clean.map((v,i)=>{const bh=Math.max(1,v/max*ih),bx=L+i*slot+(slot-bw)/2,by=T+ih-bh;const color=opts.highlight===i?'#22b58a':(opts.colors?.[i]||'#ccefe2');return `<rect x="${bx}" y="${by}" width="${bw}" height="${bh}" rx="3" fill="${color}"><title>${esc(labels[i])}: ${fmt(v,2)} kWh</title></rect>`}).join('');
 const ygrid=[0,.5,1].map(t=>`<line x1="${L}" y1="${T+ih*(1-t)}" x2="${W-R}" y2="${T+ih*(1-t)}" stroke="#edf2f3"/>`).join('');
 const step=Math.max(1,Math.ceil(labels.length/(W<400?8:12)));
 const xt=labels.map((label,i)=>i%step===0?`<text x="${L+i*slot+slot/2}" y="${H-9}" text-anchor="middle" fill="#91a2a7" font-size="9">${esc(label)}</text>`:'').join('');
 el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" width="100%" height="100%" role="img">${ygrid}${bars}${xt}</svg>`;
}
function drawTrend(history, forecast){svgLineChart($("trend-chart"),history,forecast)}
function drawProfiles(data){const hours=data.hourly_profile||[],days=data.weekday_profile||[];const peak=hours.length?hours.reduce((best,r,i,a)=>r.avg_kwh>a[best].avg_kwh?i:best,0):-1;svgBarChart($("hour-chart"),hours.map(r=>String(r.hour).padStart(2,"0")+":00"),hours.map(r=>r.avg_kwh),{highlight:peak});svgBarChart($("weekday-chart"),days.map(r=>r.day.slice(0,3)),days.map(r=>r.avg_kwh),{colors:days.map(r=>["Saturday","Sunday"].includes(r.day)?"#bfeedd":"#d7e4e7")})}
function updateSummary(summary, metrics, source){
 $("last-hour").textContent=fmt(summary.latest_hour_kwh);$("daily-total").textContent=fmt(summary.daily_average_kwh);$("forecast-total").textContent=fmt(summary.forecast_total_kwh);$("rmse").textContent=fmt(metrics.rmse,2);$("mae").textContent=fmt(metrics.mae,2);$("metric-rmse").textContent=fmt(metrics.rmse,2);$("r2").textContent=fmt(metrics.r2,3);$("history-points").textContent=Number(summary.history_points).toLocaleString();$("peak-demand").textContent=fmt(summary.peak_kwh,1);
 const change=summary.change_pct,pill=$("change-pill");pill.textContent=(change>0?"+":"")+fmt(change,1)+"%";pill.classList.toggle("negative",change>0);
 $("peak-time").textContent=summary.peak_time?new Date(summary.peak_time).toLocaleString([], {weekday:"short",month:"short",day:"numeric",hour:"numeric"}):"Peak time unavailable";
 $("outlook-text").textContent=change>8?"Demand is trending above the recent daily average. Review flexible loads during peak hours.":change < -8?"Demand is forecast below the recent daily average. This may be a useful window for planned maintenance.":"Demand is broadly aligned with the recent daily average. Keep monitoring the hourly pattern.";
 $("suggestion-text").textContent=summary.peak_kwh>summary.forecast_average_kwh*1.2?"Consider shifting non-critical equipment schedules away from the forecast peak.":"Use the hourly profile to schedule flexible loads during lower-demand periods.";
 $("source-label").textContent="Data source: "+source;$("side-source").textContent=source;
 const modelLabel=$("selected-model");if(modelLabel)modelLabel.textContent=metrics.model_name||"Selected model";
 const comparison=$("model-comparison");if(comparison&&metrics.candidates){comparison.innerHTML=metrics.candidates.map((c,i)=>`<div class="candidate-row"><span>${i===0?'<b>★</b> ':''}${esc(c.model)}</span><span>MAE <b>${fmt(c.mae,2)}</b></span><span>RMSE <b>${fmt(c.rmse,2)}</b></span></div>`).join('')}
}
async function loadDashboard(){showLoading();try{const response=await fetch("/api/dashboard");const data=await response.json();if(!response.ok)throw new Error(data.error||"Dashboard API returned "+response.status);currentDashboard=data;updateSummary(data.summary,data.metrics,data.source);drawTrend(data.history,data.forecast);drawProfiles(data);$("chart-range").textContent="Last 7 days + forecast";}catch(err){toast("Could not load dashboard: "+err.message,true);["trend-chart","hour-chart","weekday-chart"].forEach(id=>$(id).innerHTML='<div class="chart-empty">Graph unavailable. Check that the Flask server is running and reload the dashboard.</div>')}finally{hideLoading()}}
async function createForecast(){if(!currentDashboard)return;const horizon=Number($("horizon-select").value);showLoading();try{const res=await fetch("/api/forecast",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({horizon})});const data=await res.json();if(!res.ok)throw new Error(data.error||"Forecast failed");currentDashboard.forecast=data.forecast;drawTrend(currentDashboard.history,data.forecast);$("forecast-total").textContent=fmt(data.summary.forecast_total_kwh);$("peak-demand").textContent=fmt(data.summary.peak_kwh);$("peak-time").textContent=data.summary.peak_time?new Date(data.summary.peak_time).toLocaleString([], {weekday:"short",month:"short",day:"numeric",hour:"numeric"}):"Peak time unavailable";$("chart-range").textContent="Last 7 days + next "+horizon+" hours";toast("Forecast updated for the next "+horizon+" hours.")}catch(err){toast(err.message,true)}finally{hideLoading()}}
$("horizon-select").addEventListener("change",createForecast);$("refresh-btn").addEventListener("click",loadDashboard);
$("retrain-btn").addEventListener("click",async()=>{showLoading();try{const res=await fetch("/api/train",{method:"POST"});const data=await res.json();if(!res.ok)throw new Error(data.error||"Training failed");toast("Model retrained successfully using "+(data.metrics.model_name||"selected model")+".");await loadDashboard()}catch(err){toast(err.message,true)}finally{hideLoading()}});
$("upload-trigger").addEventListener("click",()=>$("dataset-file").click());
$("dataset-file").addEventListener("change",async(e)=>{const file=e.target.files[0];if(!file)return;const form=new FormData();form.append("dataset",file);showLoading();try{const res=await fetch("/api/upload",{method:"POST",body:form});const data=await res.json();if(!res.ok)throw new Error(data.error||"Upload failed");toast(data.message);await loadDashboard()}catch(err){toast(err.message,true)}finally{hideLoading();e.target.value=""}});
$("export-btn").addEventListener("click",()=>{window.location.href="/api/export";toast("Preparing forecast CSV download…")});
$("today").textContent=new Date().toLocaleDateString([], {weekday:"short",month:"short",day:"numeric",year:"numeric"});$("footer-time").textContent="UPDATED "+new Date().toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"});
window.addEventListener("resize",()=>{if(currentDashboard){drawTrend(currentDashboard.history,currentDashboard.forecast);drawProfiles(currentDashboard)}});
loadDashboard();
