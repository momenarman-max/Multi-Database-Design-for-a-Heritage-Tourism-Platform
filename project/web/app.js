const $ = id => document.getElementById(id);
const panel = $('panel'), wizard = $('wizard');
const format = new Intl.NumberFormat('ar-PS', {maximumFractionDigits:2});
let page, active, selected, busy = false;
const storageKey = 'atlas.booking.v1';

function el(tag, text, cls) {
  const node = document.createElement(tag);
  if (text != null) node.textContent = text;
  if (cls) node.className = cls;
  return node;
}
function btn(label, fn, cls='primary') {
  const node=el('button',label,cls);
  node.type='button'; node.addEventListener('click',fn); return node;
}
async function api(path, data) {
  const response=await fetch(path, data === undefined ? {} : {
    method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)
  });
  const value=await response.json();
  if (!response.ok) { const error=new Error(value.error || 'تعذّر الاتصال بالمشروع.'); error.status=response.status; throw error; }
  return value;
}
function ticket(tour) {
  const n=el('div',null,'ticket');
  n.append(el('strong',tour.name_ar),el('span',format.format(tour.price_ils)+' شيكل  ·  الزائرة نور'));
  return n;
}
async function loadSite() {
  page=await api('/api/site');
  const {site,tours}=page.MongoDB;
  $('description').textContent=site.description_ar;
  $('near').textContent=page.Neo4j.nearby.map(x=>x.name).join('، ');
  $('visits').textContent=format.format(page.PostgreSQL.stats.visits);
  $('average').textContent='★ '+format.format(page.PostgreSQL.stats.mean_rating ?? 0)+' / ٥';
  $('langs').textContent=site.languages.map(x=>({ar:'العربية',en:'الإنجليزية'})[x]||x).join('، ');
  $('offers').replaceChildren(...tours.map(t=>{
    const guide=page.Neo4j.guides.find(g=>g.id===t.guide_id)?.name || '';
    const row=el('div',null,'offer'),copy=el('div');
    copy.append(el('strong','جولة مع '+guide),el('small',t.name_ar));
    row.append(el('span',guide.charAt(0),'seal'),copy,el('b',format.format(t.price_ils)+' شيكل','cost'),
      btn('احجز الجولة',()=>openTour(t),'action')); return row;
  }));
  $('comments').replaceChildren(...page.PostgreSQL.reviews.map(r=>{
    const row=el('div',null,'review');row.append(el('span','★'.repeat(r.rating)+'☆'.repeat(5-r.rating),'stars'),el('p',r.body));return row;
  }));
}
function openPanel() {
  $('error').textContent='';
  if (!panel.open) panel.showModal();
}
function openTour(t) {
  if(active && !active.rating && active.status!=='cancelled') {openPanel(); render();return;}
  selected=t; openPanel(); render(true);
}
async function mutate(path,data) {
  if(busy)return;
  busy=true;
  const buttons=[...wizard.querySelectorAll('button')]; buttons.forEach(b=>b.disabled=true);
  try {
    active=await api(path,data); localStorage.setItem(storageKey,active.id);
    selected=page.MongoDB.tours.find(t=>t._id===active.offering_id);
    render(); await loadSite();
  } catch(e){$('error').textContent=e.message;}
  finally{busy=false;buttons.forEach(b=>b.disabled=false);}
}
function render(fresh=false) {
  wizard.replaceChildren();$('error').textContent='';
  const current=fresh?null:active;
  const step=!current?0:current.status==='cancelled'?0:current.rating?4:
    ({requested:1,confirmed:2,completed:3})[current.status];
  const labels=['طلب الحجز','تأكيد الحجز','إكمال الزيارة','تقييم الجولة','اكتملت تجربتك'];
  const title=el('h2',!selected?'حجوزاتي':current?.status==='cancelled'?'أُلغي الحجز':labels[step]);
  title.id='modalTitle';
  const steps=el('div',null,'steps');
  for(let i=0;i<5;i++)steps.append(el('span',null,i<=step?'on':''));
  wizard.append(steps,title);
  if(!selected){wizard.append(el('p','اختر إحدى الجولات المتاحة لتبدأ.'),btn('عرض الجولات',()=>{panel.close();location.hash='tours';}));return;}
  wizard.append(ticket(selected));
  const action=(verb,data={})=>mutate('/api/bookings/'+current.id+'/'+verb,data);
  if(!current)wizard.append(el('p','سيُسجّل الطلب باسم نور في قاعدة العرض المحلية.'),btn('اطلب الحجز',()=>mutate('/api/bookings',{tour:selected._id})));
  else if(current.status==='cancelled'||current.rating){
    if(current.rating)wizard.append(el('p','تقييمك: '+format.format(current.rating)+' من ٥'),el('p',current.body));
    wizard.append(btn('العودة إلى الجولات',()=>{panel.close();location.hash='tours';}));
  } else if(step===1 || step===2){
    wizard.append(el('p',step===1?'سُجّل طلبك. أكّد الحجز لتثبيت الجولة.':'حجزك مؤكد. عند انتهاء الجولة التجريبية، سجّل اكتمال الزيارة.'),
      btn(step===1?'تأكيد حجزي':'أكملت الزيارة',()=>action(step===1?'confirm':'complete')),
      btn('إلغاء الحجز',()=>action('cancel'),'secondary'));
  } else {
    let rating=5;const stars=el('div',null,'rating');
    const update=()=>[...stars.children].forEach((b,i)=>{b.textContent=i<rating?'★':'☆';b.setAttribute('aria-pressed',String(i+1===rating));});
    for(let i=1;i<=5;i++){const b=btn('★',()=>{rating=i;update();},'');b.setAttribute('aria-label','تقييم '+i+' من 5');stars.append(b);}
    update();const input=el('textarea');input.id='reviewBody';input.rows=3;input.maxLength=600;input.placeholder='ما الذي أعجبك في الجولة؟';
    const label=el('label','تعليقك');label.htmlFor=input.id;
    wizard.append(el('p','اكتملت الزيارة. شارك رأيك في الجولة.'),stars,label,input,btn('حفظ تقييمي',()=>{
      if(!input.value.trim()){$('error').textContent='أضف تعليقًا قصيرًا قبل الحفظ.';input.focus();return;}
      action('review',{rating,body:input.value.trim()});
    }));
  }
}
$('close').onclick=()=>panel.close();
$('mybooking').onclick=()=>{selected=page?.MongoDB.tours.find(t=>t._id===active?.offering_id);openPanel();render();};
async function init(){
  try{await loadSite();const id=localStorage.getItem(storageKey);
    if(id){try{active=await api('/api/bookings/'+encodeURIComponent(id));}catch(e){if(e.status===404)localStorage.removeItem(storageKey);else throw e;}}
    document.getElementById('mybooking').disabled=false;
  }catch(e){$('siteError').textContent=e.message;}
}
init();
