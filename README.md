# أطلس التراث الفلسطيني
**Multi-Database Design for a Heritage Tourism Platform**

منصة عرض محلية تربط مواقع تراثية فلسطينية بمرشدين وجولات وبيوت ضيافة. يمكن للمشغّل تسجيل زائر، طلب جولة أو إقامة، تأكيدها وإكمالها، إضافة تقييم وقراءة تحليلات الزيارة. تجمع صفحة الموقع بيانات PostgreSQL وMongoDB وNeo4j في استجابة واحدة وتستخدم Redis لتسريع الطلب التالي.

[شرائح العرض PDF](project/slides/heritage-atlas.pdf) · [سيناريو العرض](project/docs/demo.md) · [التصميم](project/docs/architecture.md) · [المستودع](https://github.com/momenarman-max/Multi-Database-Design-for-a-Heritage-Tourism-Platform)

## التشغيل على الجهاز المجهّز
من PowerShell داخل المجلد الذي يحتوي README.md:
```powershell
.\local.ps1 audit
.\local.ps1 site 00000000-0000-0000-0000-0000001e8481
.\local.ps1 analytics
.\local.ps1 test
```
يشغّل local.ps1 الخدمات المحلية عند الحاجة ويستخدم بيانات العرض المهيأة. أدلة البرامج والبيانات خارج مجلد الرفع، في مجلد work الخاص بهذه الجلسة. إذا نقلت المشروع، عيّن ATLAS_RUNTIME إلى المسار الكامل لذلك المجلد. منفذ Neo4j Browser المحلي 57474 ومنفذ Bolt المحلي 57687.

## التشغيل على جهاز جديد باستخدام Docker Compose
يتطلب Docker مع Compose v2 وحاويات Linux. من جذر المستودع:
```powershell
Copy-Item .env.example .env
docker compose build app
docker compose up -d --wait postgres mongo graph redis
docker compose run --rm app seed
docker compose run --rm app audit
docker compose run --rm app site 00000000-0000-0000-0000-0000001e8481
docker compose run --rm --entrypoint python app project/tests/integration.py
```
على Linux أو macOS استخدم `cp .env.example .env` في الخطوة الأولى. شغّل الاختبارات على قاعدة العرض المزروعة قبل إضافة زيارات يدوية، لأن بعضها يقارن أرقام العينة بنتائج محسوبة مسبقًا. أعد تنفيذ seed لإكمال تهيئة انقطعت؛ يحتفظ بالعمليات والتعديلات الموجودة. لإيقاف الحاويات مع حفظ البيانات استخدم `docker compose down`. يدخل Neo4j Browser من http://localhost:7474 باستخدام neo4j وكلمة GRAPH_PASSWORD المحلية. في نسخة Compose تُعرض منافذ الرسم على loopback فقط.

## تشغيل أصلي بديل
تستخدم التجربة Python 3.11 وPostgreSQL 16.6 وMongoDB 7.0.28 وNeo4j Community 5.26.0 وRedis. استخدم Redis 7.4 مع Compose. تم اختبار التشغيل الأصلي على Windows مع Redis 5.0.14.1. أنشئ قاعدة PostgreSQL فارغة، وثبّت المكتبات في بيئة افتراضية، ثم عرّف اتصالات الخدمات. أمثلة PowerShell لجهاز محلي ذي منافذ افتراضية:
```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
$env:PGHOST='localhost'
$env:PGDATABASE='atlas'
$env:PGUSER='atlas'
$env:PGPASSWORD=Read-Host 'Local PostgreSQL password'
$env:MONGO_URI='mongodb://localhost:27017'
$env:GRAPH_URI='bolt://localhost:7687'
$env:GRAPH_PASSWORD=Read-Host 'Local Neo4j password'
$env:REDIS_URL='redis://localhost:6379/0'
$env:PYTHONUTF8='1'
.\.venv\Scripts\python project/app/atlas.py seed
.\.venv\Scripts\python project/app/atlas.py --help
```

## جولة سريعة
كل سطر أدناه أمر بعد `docker compose run --rm app` أو `.\local.ps1`. يعيد request-booking معرّف الحجز. في أوامر المثال اللاحقة استبدل BOOKING_ID بتلك القيمة دون علامات الاقتباس.
```text
site 00000000-0000-0000-0000-0000001e8481
listing 00000000-0000-0000-0000-0000001e8481
request-booking 00000000-0000-0000-0000-0000005b8d81 tours 00000000-0000-0000-0000-0000004c4b41
confirm-booking BOOKING_ID
complete-booking BOOKING_ID
add-review BOOKING_ID 5 "أعجبني شرح المرشدة لتفاصيل السوق"
booking BOOKING_ID
analytics
```
عند حذف الموعد من الطلب يُحجز موعد فوري مناسب للعرض. لحجز مستقبلي استخدم ‎`--at 2027-05-18T10:00:00+03:00`. يمكن إلغاء الحجز المطلوب أو المؤكد بـcancel-booking. لإقامة استخدم guesthouses ومعرّف بيت الضيافة. لتفاصيل سجل العرض واختبارات الفشل راجع [دليل العرض](project/docs/demo.md).

## دليل الملفات
| المسار | المحتوى |
|---|---|
| project/app | واجهة سطر الأوامر، خدمة الحجز والصفحة، بيانات العينة، التحقق من المراجع |
| project/db | SQL وCypher وMongoDB وLua وأمثلة CRUD |
| project/tests | اختبارات تكامل على خدمات فعلية |
| project/docs | [المتطلبات](project/docs/requirements.md)، [نموذج البيانات](project/docs/data-model.md)، [القرارات والمقايضات](project/docs/decisions.md)، [معرفات العينة](project/docs/sample-ids.md) |
| project/slides | عرض PDF والنسخة القابلة للتعديل والطباعة |
| CONTRIBUTIONS.md | خطة العرض وسجل المساهمات الفعلية |

النموذج مخصص لعرض محلي ببيانات مصطنعة. إصدارات الأدوات مثبتة لتكرار التجربة. جلسات Redis توضح التخزين المؤقت للهوية في وحدة تحكم موثوقة؛ إتاحة الخدمة للزوار عبر الإنترنت تتطلب طبقة مصادقة وتفويض مستقلة.
