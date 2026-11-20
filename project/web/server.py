import json
import mimetypes
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
from uuid import UUID

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "app"))
import service
from sample import uid
from stores import sql

SITE = uid("site", 1)
VISITOR = os.getenv("ATLAS_WEB_VISITOR", uid("visitor", 1))
PORT = int(os.getenv("ATLAS_WEB_PORT", "8765"))
HOST = f"127.0.0.1:{PORT}"
ASSETS = {"index.html", "style.css", "app.js", "market.jpg"}


def booking(key):
    with sql() as conn:
        row = conn.execute("""SELECT b.id,b.status,b.offering_id,r.rating,r.body
            FROM bookings b LEFT JOIN reviews r ON r.booking_id=b.id
            WHERE b.id=%s AND b.visitor_id=%s AND b.site_id=%s""", (UUID(key), VISITOR, SITE)).fetchone()
    if not row:
        raise ValueError("تعذّر العثور على هذا الحجز.")
    return row


class Handler(BaseHTTPRequestHandler):
    def reply(self, data, status=200, mime="application/json; charset=utf-8"):
        body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.headers.get("Host") != HOST:
            return self.reply({}, 403)
        path = urlsplit(self.path).path
        try:
            if path == "/api/site":
                return self.reply(service.site(SITE))
            if path.startswith("/api/bookings/"):
                return self.reply(booking(path.rsplit("/", 1)[1]))
            if path == "/health":
                return self.reply({"application":"heritage-atlas-web"})
            file = path[1:] or "index.html"
            if file not in ASSETS or not (HERE/file).is_file():
                return self.reply({}, 404)
            self.reply((HERE/file).read_bytes(), mime=mimetypes.guess_type(file)[0] or "application/octet-stream")
        except ValueError:
            self.reply({"error":"تعذّر العثور على الحجز."}, 404)
        except Exception:
            self.reply({"error":"تعذّر الاتصال بمصادر بيانات المشروع. أعد فتح المشغّل."}, 503)

    def do_POST(self):
        if self.headers.get("Host") != HOST or self.headers.get("Origin") != "http://"+HOST:
            return self.reply({}, 403)
        try:
            length = int(self.headers.get("Content-Length", 0))
            if not 0 < length <= 8192 or self.headers.get_content_type() != "application/json":
                return self.reply({}, 400)
            data = json.loads(self.rfile.read(length))
            if self.path == "/api/bookings":
                tour = str(UUID(data["tour"]))
                if SITE not in service.one("tours", tour)["site_ids"]:
                    raise ValueError()
                return self.reply(booking(service.request(VISITOR, "tours", tour)), 201)
            parts = self.path.strip("/").split("/")
            if len(parts) != 4 or parts[:2] != ["api","bookings"]:
                return self.reply({}, 404)
            key, action = parts[2:]
            booking(key)
            if action == "review":
                rating, body = data["rating"], str(data["body"]).strip()
                if type(rating) is not int or not 1 <= rating <= 5 or not 1 <= len(body) <= 600:
                    raise ValueError()
                service.review(key, rating, body)
            elif action in ("confirm","complete","cancel"):
                service.transition(key, {"confirm":"confirmed","complete":"completed","cancel":"cancelled"}[action])
            else:
                return self.reply({}, 404)
            self.reply(booking(key))
        except (KeyError, ValueError, TypeError):
            self.reply({"error":"تعذّر تنفيذ الخطوة. تحقق من حالة الحجز والبيانات المدخلة."}, 400)
        except Exception:
            self.reply({"error":"تعذّر إتمام الطلب. حدّث الصفحة للتحقق من حالة الحجز."}, 503)


if __name__ == "__main__":
    ThreadingHTTPServer((os.getenv("ATLAS_WEB_BIND", "127.0.0.1"),PORT),Handler).serve_forever()
