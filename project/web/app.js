'use strict';
const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const arabic = value => Number(value).toLocaleString('ar-PS',{maximumFractionDigits:2});
const date = value => new Date(value).toLocaleString('ar-PS');
const states = {requested:'قيد الطلب', confirmed:'مؤكد', completed:'مكتمل', cancelled:'ملغى'};
let catalog, me, pending, revision=0;
const view=$('#view'), dialog=$('dialog');
const item=(kind,id)=>catalog[kind].find(row=>row._id===id || row.id===id);
const city=id=>item('cities',id)?.name || '';
const linkSite=id=>'#/site/'+encodeURIComponent(id);
async function api(path,data){
 const options=data===undefined?{}:{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)};
 const response=await fetch('/api/'+path,options), result=await response.json();
 if(!response.ok) throw Error(result.error || 'تعذر تنفيذ الطلب. حاول مرة أخرى.');
 return result;
}
function modal(title,html){$('#dialogTitle').textContent=title;$('#panel').innerHTML=html;$('.error').textContent='';if(!dialog.open)dialog.showModal();}
function account(){ $('#account').textContent=me?me.name+' · حسابي':'دخول الزوار';}
function auth(create=false){
 modal(create?'إنشاء حساب زائر':'تسجيل الدخول','<form id="auth">'+(create?'<label>الاسم<input name="name" maxlength="80" required autocomplete="name"></label>':'')+'<label>البريد الإلكتروني<input type="email" name="email" required autocomplete="email" dir="ltr"></label><label>كلمة المرور<input type="password" name="password" minlength="8" maxlength="128" required autocomplete="'+(create?'new':'current')+'-password" dir="ltr"></label>'+(create?'<fieldset><legend>اهتماماتك</legend>'+['آثار','حرف','عمارة'].map(x=>'<label><input type="checkbox" name="interest" value="'+x+'"> '+x+'</label>').join('')+'</fieldset>':'')+'<button class="primary" value="'+(create?'register':'login')+'">'+(create?'إنشاء الحساب':'دخول')+'</button> <button type="button" class="secondary" data-act="'+(create?'login':'register')+'">'+(create?'لدي حساب':'إنشاء حساب جديد')+'</button></form>');
}
const destinationPhotos={
 'البلدة القديمة في الخليل':['hebron-old.jpg','سوق في البلدة القديمة بالخليل'],
 'سوق القزازين':['hebron-glass.jpg','من حرفة المدينة: الزجاج الخليلي'],
 'حارة العقابة':['aqaba.jpg','حارة العقابة التاريخية · الخليل'],
 'ساحة المهد':['manger.jpg','ساحة المهد · بيت لحم'],
 'شارع النجمة':['star.jpg','شارع النجمة · بيت لحم'],
 'بيت ساحور القديمة':['sahour.jpg','داخل بيت في بيت ساحور · صورة تاريخية'],
 'البلدة القديمة في نابلس':['nablus-old.jpg','البلدة القديمة · نابلس'],
 'خان الوكالة':['nablus-street.jpg','من محيط الخان: البلدة القديمة في نابلس'],
 'تل الرميدة':['rumeida.jpg','بقايا البركة الغربية في تل الرميدة · الخليل']
};
function placePhoto(site){
 const photo=destinationPhotos[site.name_ar];
 if(!photo)return '';
 return '<figure class="place-photo"><img src="/'+photo[0]+'" alt="'+photo[1]+'"><figcaption>'+photo[1]+'</figcaption></figure>';
}
function mountGallery(){
 const figure=view.querySelector('.hero figure');
 const photos=[destinationPhotos['ساحة المهد'],destinationPhotos['حارة العقابة'],destinationPhotos['البلدة القديمة في نابلس'],
  ...Object.values(destinationPhotos).filter(photo=>!['manger.jpg','aqaba.jpg','nablus-old.jpg'].includes(photo[0])),
  ['hebron.jpg','الحرم الإبراهيمي · الخليل'],['bethlehem.jpg','كنيسة المهد · بيت لحم'],
  ['Nablus_Great_Mosque.jpg','مئذنة الجامع الكبير · نابلس، صورة تاريخية'],
  ['Palestine-2013-Aerial-Mar_Saba_Monastery.jpg','دير مار سابا · شرق بيت لحم']];
 figure.className='heritage-gallery';
 figure.setAttribute('aria-live','off');
 figure.innerHTML=photos.map(([file,title],i)=>'<img src="/'+file+'" alt="'+title+'" class="'+(i===0?'current':'')+'" aria-hidden="'+(i!==0)+'">').join('')+
 '<figcaption></figcaption><button type="button" class="gallery-play">إيقاف العرض</button>';
 const slides=Array.from(figure.querySelectorAll('img')),caption=figure.querySelector('figcaption'),button=figure.querySelector('button');
 let current=0, timer;
 caption.textContent=photos[current][1];
 function advance(){
  if(!figure.isConnected){clearInterval(timer);return;}
  slides[current].classList.remove('current');slides[current].setAttribute('aria-hidden','true');
  current=(current+1)%slides.length;
  slides[current].classList.add('current');slides[current].setAttribute('aria-hidden','false');
  caption.textContent=photos[current][1];
 }
 function play(){timer=setInterval(advance,2000);button.textContent='إيقاف العرض';}
 button.onclick=()=>{
  if(timer){clearInterval(timer);timer=null;button.textContent='تشغيل العرض';}else play();
 };
 play();
}
function home(){
 view.innerHTML='<section class="hero"><div class="heroCopy"><p class="location">دليل السياحة التراثية في فلسطين</p><h1>اكتشف فلسطين<br>على مهل</h1><p>تجوّل بين أسواق الخليل وأزقة نابلس وحارات بيت لحم. اختر موقعًا وتعرّف إلى حكايته ومرشديه وبيوت الضيافة القريبة.</p><button class="gold" data-act="explore">استكشف الوجهات ↓</button></div><figure></figure></section><section class="section"><h2>دليل الوجهات</h2><div class="filters"><label>ابحث عن موقع<input id="search" type="search" placeholder="اسم الموقع أو وصفه"></label><label>المدينة<select id="city"><option value="">كل المدن</option>'+catalog.cities.map(c=>'<option value="'+esc(c.id)+'">'+esc(c.name)+'</option>').join('')+'</select></label><label>التراث<select id="tag"><option value="">كل الأنواع</option>'+['آثار','حرف','عمارة'].map(x=>'<option>'+x+'</option>').join('')+'</select></label></div><p id="count"></p><div class="grid" id="cards"></div></section>';
 mountGallery();
 for(const id of ['search','city','tag']) $('#'+id).oninput=cards;
 cards();
}
function cards(){
 const rows=catalog.sites.filter(s=>(!$('#city').value||s.city_id===$('#city').value)&&(!$('#tag').value||s.tags.includes($('#tag').value))&&(s.name_ar+' '+s.description_ar).includes($('#search').value.trim()));
 $('#count').textContent=arabic(rows.length)+' وجهات مطابقة';
 $('#cards').innerHTML=rows.map(s=>'<a class="card" href="'+linkSite(s._id)+'">'+placePhoto(s)+'<small>'+esc(city(s.city_id))+' · '+esc(s.tags.join('، '))+'</small><h3>'+esc(s.name_ar)+'</h3><p>'+esc(s.description_ar)+'</p><b>استكشف الموقع ←</b></a>').join('')||'جرّب تغيير المدينة أو نوع التراث.';
}
function offers(rows,kind){
 return rows.map(o=>{const tour=kind==='tours', g=tour?item('guides',o.guide_id):null;
 return '<article class="offer"><div><strong>'+esc(o.name_ar)+'</strong><p>'+esc(tour?'المرشد '+g.name_ar+' · '+g.services.join('، ')+' · العربية والإنجليزية':o.description_ar+' · '+[...o.rooms,...o.amenities].join('، '))+'</p>'+(tour?'<small>جولة مشي في '+esc(o.site_ids.map(id=>item('sites',id).name_ar).join('، '))+' · '+arabic(o.price_ils)+' شيكل</small>':'')+'</div><button class="action" data-act="book" data-kind="'+kind+'" data-id="'+esc(o._id)+'">'+(tour?'احجز الجولة':'احجز الإقامة')+'</button></article>';}).join('')||'<p>لا تتوفر خيارات مسجّلة في هذا الموقع حاليًا.</p>';
}
function itinerary(s){
 const stops={
 'البلدة القديمة في الخليل':['ابدأ عند مدخل السوق واقرأ شكل القوس الحجري.','تتبّع مع المرشد كيف تتفرع الحارات عن طريق السوق.','توقّف عند واجهة حانوت وناقش صلة الحرفة بالمكان.'],
 'سوق القزازين':['تعرّف إلى تسمية السوق مع المرشد.','قارن واجهات المحال ومداخلها.','اسأل عن الحرف التي يتذكّرها أهل السوق.'],
 'حارة العقابة':['تأمّل شكل الزقاق من مدخله.','قارن الأقواس والأبواب على امتداد الحارة.','ارسم مخططًا بسيطًا للعلاقة بين الطريق والفناء.'],
 'ساحة المهد':['ابدأ بمشهد عام للساحة.','تتبّع اتجاهات الطرق المتصلة بها.','ناقش دور الساحة في لقاء السكان والزوار.'],
 'شارع النجمة':['ابدأ من واجهة حجرية تطل على الطريق.','تتبّع تفاصيل الأبواب والنوافذ.','قارن بين استعمال الطابق الأرضي والعلوي.'],
 'بيت ساحور القديمة':['انطلق من أحد أزقة البلدة.','تعرّف إلى خشب الزيتون واستخداماته في الحرفة المحلية.','استمع إلى حكاية عن انتقال الحرفة بين الأجيال.'],
 'البلدة القديمة في نابلس':['تتبّع مسارًا يربط السوق بالخانات.','لاحظ كيف يتغير إيقاع الشارع بين المحال والأفنية.','ناقش دور الحرفيين في حياة السوق.'],
 'خان الوكالة':['تأمّل مدخل الخان.','انتقل إلى قراءة الفناء وعلاقته بالغرف المحيطة.','ناقش كيف خدم هذا التنظيم حركة الزوار والتجار.'],
 'تل الرميدة':['ابدأ بتحديد موضع التل بالنسبة إلى مدينة الخليل.','ناقش كيف يميّز الأثريون بين طبقات الاستيطان.','اختم برسم يربط تضاريس المكان بنشأة التجمعات السكنية.']
 };
 return '<h2>مسار مقترح للزيارة</h2><ol>'+ (stops[s.name_ar]||[]).map(stop=>'<li>'+esc(stop)+'</li>').join('')+'</ol>';
}
function site(data){
 const {site:s,tours,guesthouses}=data.MongoDB,{stats,reviews}=data.PostgreSQL,{nearby,guides}=data.Neo4j;
 return '<section class="section"><a href="#/">→ دليل الوجهات</a><div class="intro"><small>'+esc(city(s.city_id))+' / '+esc(s.tags.join('، '))+'</small><h1>'+esc(s.name_ar)+'</h1>'+placePhoto(s)+'<p>'+esc(s.description_ar)+'</p></div><div class="content"><div><h2>عن المكان وتراثه</h2><p>'+esc(s.description_ar)+'</p>'+(s._id===catalog.sites[0]._id?'<p>تحتفظ البلدة القديمة بنسيج عمراني تشكّل في العصر المملوكي، وتكشف أسواقها وحاراتها علاقة التجارة بالحياة اليومية حول الحرم الإبراهيمي. أُدرجت على قائمة التراث العالمي عام ٢٠١٧. <a class="under" href="https://whc.unesco.org/en/list/1565/">صفحة الموقع لدى اليونسكو</a></p>':'')+itinerary(s)+'<h2>جولات مع المرشدين</h2>'+offers(tours,'tours')+'<h2>بيوت الضيافة</h2>'+offers(guesthouses,'guesthouses')+'<h2>تقييمات الزوار</h2>'+reviews.map(r=>'<div class="review"><b class="stars">'+arabic(r.rating)+' / ٥ ★</b><p>'+esc(r.body)+'</p></div>').join('')+(reviews.length?'':'كن أول من يقيّم خدمة بعد إكمال حجزها.')+'</div><aside class="facts"><h2>دليل الزيارة</h2><p>'+esc(s.opening_info)+'</p><dl><div><dt>زيارات مكتملة</dt><dd>'+arabic(stats.visits)+'</dd></div><div><dt>متوسط التقييم</dt><dd>'+(stats.mean_rating?arabic(stats.mean_rating)+' / ٥':'لا تقييمات')+'</dd></div></dl><h3>مرشدون يخدمون المنطقة</h3><p>'+esc(guides.map(g=>g.name).join('، ')||'لا يوجد مرشد مدرج')+'</p><h3>مواقع قريبة</h3>'+nearby.map(n=>'<a class="under" href="'+linkSite(n.id)+'">'+esc(n.name)+'</a>').join(' · ')+(nearby.length?'':'لا توجد مواقع مرتبطة حاليًا.')+'</aside></div></section>';
}
function bookingForm(kind,id){
 if(!me){pending={kind,id};return auth();}
 const stay=kind==='guesthouses',o=item(kind,id);
 modal(stay?'حجز إقامة':'حجز جولة','<div class="ticket"><strong>'+esc(o.name_ar)+'</strong>'+esc(stay?o.amenities.join(' · '):arabic(o.price_ils)+' شيكل')+'</div><form id="booking" data-kind="'+kind+'" data-id="'+esc(id)+'"><label>نوع الموعد<select name="mode"><option value="demo">تجربة فورية للحجز والتقييم</option><option value="scheduled">تحديد موعد مستقبلي</option></select></label><div id="dates" hidden><label>'+(stay?'موعد الوصول':'موعد الجولة')+'<input type="datetime-local" name="at"></label>'+(stay?'<label>موعد المغادرة<input type="datetime-local" name="departure"></label>':'')+'</div><button class="primary">إرسال طلب الحجز</button></form>');
 const form=$('#booking');form.elements.mode.onchange=()=>{const active=form.elements.mode.value==='scheduled';$('#dates').hidden=!active;for(const input of $('#dates').querySelectorAll('input'))input.required=active;};
}
function action(label,act,id){return '<button class="secondary" data-act="'+act+'" data-id="'+esc(id)+'">'+label+'</button>';}
function bookings(rows){
 return '<section class="section"><h1>حجوزاتي</h1><p>تابع طلبات الجولات والإقامات هنا. تتيح لك التجربة محاكاة تأكيد مقدم الخدمة وتسجيل اكتمال الزيارة.</p>'+rows.map(b=>{
 const o=item(b.offering_type,b.offering_id),due=new Date(b.departure_at||b.service_at)<=new Date();
 return '<article class="card"><small>'+esc(states[b.status])+' · '+(b.offering_type==='tours'?'جولة':'إقامة')+'</small><h3>'+esc(o?.name_ar)+'</h3><p>'+esc(date(b.service_at))+(b.departure_at?' — '+esc(date(b.departure_at)):'')+'</p><a class="under" href="'+linkSite(b.site_id)+'">تفاصيل الموقع</a> '+(b.status==='requested'?action('تأكيد الحجز التجريبي','confirm',b.id):'')+(b.status==='confirmed'&&due?action('تسجيل اكتمال الزيارة','complete',b.id):'')+(['requested','confirmed'].includes(b.status)?action('إلغاء الحجز','cancel',b.id):'')+(b.status==='completed'&&!b.rating?action('قيّم الخدمة','review',b.id):'')+(b.rating?'<p>تقييمك ★ '+arabic(b.rating)+' / ٥ · '+esc(b.body)+'</p>':'')+'</article>';}).join('')+(rows.length?'':'<p>لم تحجز بعد. <a class="under" href="#/">استكشف الوجهات</a></p>')+'</section>';
}
function analytics(a){
 const ranking=(title,rows,label,field,max)=>'<article class="card"><h2>'+title+'</h2>'+rows.map(r=>'<div class="rank"><span>'+esc(label(r))+'</span><b>'+arabic(r[field])+'</b><progress value="'+Number(r[field])+'" max="'+max+'"></progress></div>').join('')+(rows.length?'':'لا توجد بيانات بعد.')+'</article>';
 const quarters=['كانون الثاني – آذار','نيسان – حزيران','تموز – أيلول','تشرين الأول – كانون الأول'];
 return '<section class="section"><h1>إحصاءات السياحة</h1><p>تُحسب الزيارات عند إكمال الحجز. تجمع هذه اللوحة بيانات العينة وتجارب الزوار على هذه النسخة.</p><div class="intro"><h2>رضا الزوار</h2><strong>'+ (a.satisfaction.total?arabic(100*a.satisfaction.positive/a.satisfaction.total)+'٪':'—')+'</strong><p>من التقييمات أعطت الخدمة أربع نجوم أو خمسًا. المتوسط '+(a.satisfaction.mean?arabic(a.satisfaction.mean):'—')+' من ٥ عبر '+arabic(a.satisfaction.total)+' تقييمات.</p></div><div class="grid">'+ranking('المواقع الأكثر زيارة',a.most_visited,r=>item('sites',r.site_id)?.name_ar,'visits',a.most_visited[0]?.visits||1)+ranking('مواسم الذروة',a.peak_quarters,r=>quarters[r.quarter-1],'visits',a.peak_quarters[0]?.visits||1)+ranking('تقييمات المرشدين',a.guide_ratings,r=>item('guides',r.guide_id)?.name_ar,'rating',5)+ranking('تقييمات المواقع',a.site_ratings,r=>item('sites',r.site_id)?.name_ar,'rating',5)+'</div></section>';
}
async function route(){
 const rev=++revision,path=location.hash.slice(1)||'/';
 try{if(path==='/'){home();}else if(path==='/bookings'&&!me){view.innerHTML='<section class="section"><h1>حجوزاتي</h1><p>سجّل الدخول لعرض حجوزاتك وتقييماتك.</p><button class="primary" data-act="login">تسجيل الدخول</button></section>';}else{
 const page=path==='/bookings'?bookings:path==='/analytics'?analytics:path.startsWith('/site/')?site:null;
 if(!page){location.hash='/';return;}
 const data=await api(page===site?'sites/'+encodeURIComponent(path.split('/')[2]):path.slice(1));
 if(rev!==revision)return;view.innerHTML=page(data);}
 for(const a of document.querySelectorAll('nav a')){
  if(a.hash==='#'+path || (path.startsWith('/site/') && a.hash==='#/'))a.setAttribute('aria-current','page');else a.removeAttribute('aria-current');
 }
 if(!matchMedia('(prefers-reduced-motion: reduce)').matches) view.firstElementChild?.animate([{opacity:.45,transform:'translateY(7px)'},{opacity:1,transform:'translateY(0)'}],{duration:240,easing:'ease-out'});
 window.scrollTo({top:0,behavior:'instant'});
 }catch(e){if(rev===revision)view.textContent=e.message;}
}
$('#close').onclick=()=>dialog.close();dialog.addEventListener('close',()=>{if(!dialog.open)pending=null;});
$('#account').onclick=()=>me?modal('حساب الزائر','<p>'+esc(me.name)+'</p><button class="primary" data-act="logout">تسجيل الخروج</button>'):auth();
document.addEventListener('click',async event=>{
 const b=event.target.closest('[data-act]');if(!b||b.disabled)return;
 const act=b.dataset.act,id=b.dataset.id;
 if(act==='explore'){ $('#search').focus();return;}
 if(act==='login'||act==='register')return auth(act==='register');
 if(act==='book')return bookingForm(b.dataset.kind,id);
 if(act==='review')return modal('تقييم الخدمة','<form id="rating" data-id="'+esc(id)+'"><label>النجوم<select name="rating">'+[5,4,3,2,1].map(n=>'<option value="'+n+'">'+arabic(n)+' ★</option>').join('')+'</select></label><label>تعليقك<textarea name="body" maxlength="600" required></textarea></label><button class="primary">حفظ تقييمي</button></form>');
 b.disabled=true;
 try{if(act==='logout'){await api('logout',{});me=null;account();dialog.close();}
 else await api('bookings/'+id+'/'+act,{});await route();}
 catch(e){modal('تعذّر تنفيذ الطلب','<p>'+esc(e.message)+'</p>');}finally{b.disabled=false;}
});
document.addEventListener('submit',async event=>{
 event.preventDefault();const f=event.target,button=event.submitter;if(!button||button.disabled)return;button.disabled=true;
 const data=Object.fromEntries(new FormData(f));
 try{if(f.id==='auth'){me=await api(button.value,{...data,interests:new FormData(f).getAll('interest')});account();
 if(pending){const p=pending;pending=null;return bookingForm(p.kind,p.id);}}
 if(f.id==='booking'){const schedule=data.mode==='scheduled';await api('bookings',{kind:f.dataset.kind,offering:f.dataset.id,at:schedule?new Date(data.at).toISOString():null,departure:schedule&&data.departure?new Date(data.departure).toISOString():null});location.hash='/bookings';}
 if(f.id==='rating')await api('bookings/'+f.dataset.id+'/review',{rating:Number(data.rating),body:data.body});
 dialog.close();await route();}catch(e){$('.error').textContent=e.message;}finally{button.disabled=false;}
});
async function start(){try{[catalog,me]=await Promise.all([api('catalog'),api('me')]);account();await route();}catch(e){view.textContent=e.message;}}
window.addEventListener('hashchange',route);start();






