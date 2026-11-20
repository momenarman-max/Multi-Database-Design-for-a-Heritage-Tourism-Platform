"""Local heritage tourism platform. Run seed before starting the HTTP service."""
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import sys
from datetime import datetime
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from psycopg.errors import UniqueViolation

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "app"))
import service
from stores import cache, cypher, docs, source, sql

PORT = int(os.getenv("ATLAS_WEB_PORT", "8765"))
HOST = f"127.0.0.1:{PORT}"
ASSETS = {'bethlehem.jpg', 'star.jpg', 'nablus-old.jpg', 'Nablus_Great_Mosque.jpg', 'hebron.jpg', 'nablus-street.jpg', 'style.css', 'sahour.jpg', 'index.html', 'manger.jpg', 'hebron-glass.jpg', 'app.js', 'Palestine-2013-Aerial-Mar_Saba_Monastery.jpg', 'aqaba.jpg', 'rumeida.jpg', 'hebron-old.jpg'}
TTL = 7200


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1, dklen=32)


def catalog():
    return {"cities":cypher("MATCH (c:City) RETURN c.id AS id,c.name AS name ORDER BY c.name"),
            "sites":list(docs.sites.find().sort("_id",1)), "guides":list(docs.guides.find()),
            "tours":list(docs.tours.find()), "guesthouses":list(docs.guesthouses.find())}


def profile(visitor):
    if visitor:
        with sql() as c:
            return c.execute("SELECT id,name,interests,languages FROM visitors WHERE id=%s",(visitor,)).fetchone()


def my_bookings(visitor):
    with sql() as c:
        return c.execute("""SELECT b.id,b.offering_id,b.offering_type,b.site_id,b.status,b.service_at,
            b.departure_at,r.rating,r.body FROM bookings b LEFT JOIN reviews r ON r.booking_id=b.id
            WHERE b.visitor_id=%s ORDER BY b.requested_at DESC,b.id""",(visitor,)).fetchall()


class Handler(BaseHTTPRequestHandler):
    def reply(self,data,status=200,mime="application/json; charset=utf-8",cookie=None):
        raw=data if isinstance(data,bytes) else json.dumps(data,ensure_ascii=False,default=str).encode()
        self.send_response(status)
        for name,value in {"Content-Type":mime,"Content-Length":str(len(raw)),"Cache-Control":"no-store",
                "X-Content-Type-Options":"nosniff","Content-Security-Policy":
                "default-src 'self'; object-src 'none'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"}.items():
            self.send_header(name,value)
        if cookie is not None:
            self.send_header("Set-Cookie",f"atlas_sid={cookie}; Path=/; HttpOnly; SameSite=Strict; Max-Age={TTL if cookie else 0}")
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (ConnectionResetError,ConnectionAbortedError,BrokenPipeError):
            pass

    def token(self):
        jar=SimpleCookie()
        jar.load(self.headers.get("Cookie",""))
        item=jar.get("atlas_sid")
        return item.value if item and re.fullmatch(r"[A-Za-z0-9_-]{43}",item.value) else ""

    def visitor(self):
        token=self.token()
        return cache.get("web:session:"+token) if token else None

    def do_GET(self):
        if self.headers.get("Host")!=HOST:
            return self.reply({},403)
        path=urlsplit(self.path).path
        try:
            if path=="/health":
                return self.reply({"application":"heritage-atlas-platform"})
            if path=="/api/catalog":
                return self.reply(catalog())
            if path.startswith("/api/sites/"):
                return self.reply(service.site(str(UUID(path.split("/")[-1]))))
            if path=="/api/me":
                return self.reply(profile(self.visitor()))
            if path in ("/api/bookings","/api/recommendations"):
                visitor=self.visitor()
                if not visitor:
                    return self.reply({"error":"سجّل الدخول أولًا."},401)
                return self.reply(my_bookings(visitor) if path=="/api/bookings" else
                                  cypher(source("neo4j/recommend.cypher"),id=visitor))
            if path=="/api/analytics":
                data=service.analytics()
                with sql() as c:
                    data["satisfaction"]=c.execute("""SELECT count(*) AS total,round(avg(rating),2) AS mean,
                        count(*) FILTER(WHERE rating>=4) AS positive FROM reviews""").fetchone()
                return self.reply(data)
            name=path[1:] or "index.html"
            if name in ASSETS:
                return self.reply((HERE/name).read_bytes(),mime=mimetypes.guess_type(name)[0])
            return self.reply({},404)
        except ValueError:
            self.reply({"error":"الموقع غير موجود."},404)
        except Exception:
            self.reply({"error":"تعذّر تحميل البيانات. تحقق من اتصال الخدمات."},503)

    def auth(self, data, create):
        email=data.get("email","").strip().lower()
        password=data.get("password","")
        if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+",email) or len(email)>254 or not 8<=len(password)<=128:
            raise ValueError("أدخل بريدًا صحيحًا وكلمة مرور من 8 إلى 128 حرفًا.")
        bucket="web:login:"+hashlib.sha256(email.encode()).hexdigest()
        if not create and int(cache.get(bucket) or 0)>=10:
            return self.reply({"error":"محاولات دخول كثيرة. حاول بعد خمس دقائق."},429)
        if create:
            name=data.get("name","").strip()
            interests=data.get("interests",[])
            language=data.get("language","ar")
            if not 1<=len(name)<=80 or language not in ("ar","en") or not isinstance(interests,list) or not set(interests)<= {"عمارة","حرف","آثار"}:
                raise ValueError("تحقق من الاسم والاهتمامات واللغة.")
            visitor=str(uuid4())
            salt=secrets.token_bytes(16)
            with sql() as c:
                c.execute("INSERT INTO visitors VALUES (%s,%s,%s,%s,%s)",(visitor,name,email,interests,[language]))
                c.execute("INSERT INTO web_credentials VALUES (%s,%s,%s)",(visitor,salt,password_hash(password,salt)))
            service.sync()
        else:
            with sql() as c:
                row=c.execute("""SELECT v.id,w.salt,w.verifier FROM visitors v JOIN web_credentials w
                    ON v.id=w.visitor_id WHERE v.email=%s""",(email,)).fetchone()
            digest=password_hash(password,bytes(row["salt"]) if row else bytes(16))
            if not row or not hmac.compare_digest(digest,bytes(row["verifier"])):
                with cache.pipeline() as pipe:
                    pipe.incr(bucket).expire(bucket,300).execute()
                return self.reply({"error":"تعذّر الدخول بهذا البريد وكلمة المرور."},401)
            visitor=str(row["id"])
            cache.delete(bucket)
        token=secrets.token_urlsafe(32)
        cache.set("web:session:"+token,visitor,ex=TTL)
        return self.reply(profile(visitor),cookie=token)

    def do_POST(self):
        if self.headers.get("Host")!=HOST or self.headers.get("Origin")!="http://"+HOST:
            return self.reply({},403)
        try:
            length=int(self.headers.get("Content-Length",0))
            if not 0<length<=8192 or self.headers.get_content_type()!="application/json":
                return self.reply({},400)
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict):
                raise ValueError("طلب غير صالح.")
            if self.path in ("/api/register","/api/login"):
                return self.auth(data,self.path=="/api/register")
            if self.path=="/api/logout":
                cache.delete("web:session:"+self.token())
                return self.reply({},cookie="")
            visitor=self.visitor()
            if not visitor:
                return self.reply({"error":"سجّل الدخول لإتمام الحجز."},401)
            if self.path=="/api/bookings":
                kind=data["kind"]
                at=data.get("at") or None
                end=data.get("departure") or None
                if any(datetime.fromisoformat(t).tzinfo is None for t in (at,end) if t):
                    raise ValueError("تحقق من توقيت الموعد.")
                if end and (kind!="guesthouses" or not at or datetime.fromisoformat(end)<=datetime.fromisoformat(at)):
                    raise ValueError("المغادرة يجب أن تكون بعد الوصول.")
                if kind=="guesthouses" and bool(at)!=bool(end):
                    raise ValueError("حدّد الوصول والمغادرة معًا.")
                result=service.request(visitor,kind,str(UUID(data["offering"])),at,end)
                return self.reply({"id":result},201)
            parts=self.path.strip("/").split("/")
            if len(parts)!=4 or parts[:2]!=["api","bookings"]:
                return self.reply({},404)
            key=str(UUID(parts[2]))
            with sql() as c:
                if not c.execute("SELECT 1 FROM bookings WHERE id=%s AND visitor_id=%s",(key,visitor)).fetchone():
                    return self.reply({"error":"الحجز غير موجود في حسابك."},404)
            action=parts[3]
            if action=="review":
                rating=data["rating"]
                body=data["body"].strip()
                if type(rating)!=int or not 1<=rating<=5 or not 1<=len(body)<=600:
                    raise ValueError("أدخل تقييمًا من 1 إلى 5 وتعليقًا قصيرًا.")
                return self.reply(service.review(key,rating,body))
            if action not in ("confirm","complete","cancel"):
                return self.reply({},404)
            return self.reply(service.transition(key,{"confirm":"confirmed","complete":"completed","cancel":"cancelled"}[action]))
        except UniqueViolation:
            self.reply({"error":"هذا البريد مسجّل أو سبق تقييم الحجز."},409)
        except (ValueError,TypeError,AttributeError,KeyError) as exc:
            msg=str(exc)
            self.reply({"error":msg if re.search("[ء-ي]",msg) else "تعذّر تنفيذ الطلب. تحقق من الموعد وحالة الحجز."},400)
        except Exception:
            self.reply({"error":"تعذّر الاتصال بالخدمات. راجع حجوزاتك قبل إعادة الطلب."},503)


if __name__=="__main__":
    ThreadingHTTPServer((os.getenv("ATLAS_WEB_BIND","127.0.0.1"),PORT),Handler).serve_forever()



