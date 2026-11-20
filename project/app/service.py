import json
import secrets
from datetime import datetime, timezone
from uuid import uuid4

from stores import cache, cached, cypher, docs, invalidate, page_key, source, sql


def one(collection, key):
    result = docs[collection].find_one({"_id": str(key)})
    if result is None:
        raise ValueError(f"Unknown {collection} identifier: {key}")
    return result


def sync():
    """Repair visitor projections and replay each pending visit in commit order."""
    with sql() as c:
        visitors = c.execute("SELECT id,name,interests FROM visitors").fetchall()
        cypher("""UNWIND $rows AS row MERGE (v:Visitor {id:row.id})
                  SET v.name=row.name,v.interests=row.interests""",
               rows=[dict(v, id=str(v["id"])) for v in visitors])
        pending = c.execute("""SELECT e.id,e.site_id,e.visited_at,b.visitor_id FROM visit_events e
            JOIN bookings b ON b.id=e.booking_id WHERE NOT e.projected
            ORDER BY e.visited_at,e.id FOR UPDATE OF e""").fetchall()
        for row in pending:
            result = cypher("""MATCH (v:Visitor {id:$v}),(s:Site {id:$s})
                MERGE (v)-[r:VISITED]->(s)
                SET r.visited_at=CASE WHEN r.visited_at IS NULL OR r.visited_at < datetime($at)
                THEN datetime($at) ELSE r.visited_at END RETURN s.id AS id""",
                v=str(row["visitor_id"]), s=str(row["site_id"]), at=row["visited_at"].isoformat())
            if not result:
                raise ValueError("Missing endpoint while projecting visit")
            c.execute("UPDATE visit_events SET projected=true WHERE id=%s", (row["id"],))
    return {"visits_projected": len(pending)}


def register(name, email, interests, languages):
    if not name.strip() or "@" not in email or not languages:
        raise ValueError("Specify a name, email and language")
    key = str(uuid4())
    with sql() as c:
        c.execute("INSERT INTO visitors VALUES (%s,%s,%s,%s,%s)",
                  (key, name.strip(), email.strip().lower(), interests, languages))
    sync()
    return key


def request(visitor, kind, offering, at=None, departure=None):
    if kind not in ("tours", "guesthouses"):
        raise ValueError("Select tours or guesthouses")
    item = one(kind, offering)
    site = item["site_ids"][0] if kind == "tours" else item["site_id"]
    one("sites", site)
    guide = item.get("guide_id")
    if guide:
        one("guides", guide)
    now = datetime.now(timezone.utc)
    service_at = datetime.fromisoformat(at) if at else now
    if service_at.tzinfo is None or service_at < now:
        raise ValueError("Specify a future service time with a UTC offset, or omit for a walk-in")
    key = str(uuid4())
    with sql() as c:
        c.execute("""INSERT INTO bookings(id,visitor_id,offering_id,offering_type,site_id,
                    guide_id,requested_at,service_at,departure_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                  (key, visitor, offering, kind, site, guide, now, service_at, departure))
    return key


def transition(key, target):
    allowed = {"confirmed": ["requested"], "completed": ["confirmed"], "cancelled": ["requested","confirmed"]}
    with sql() as c:
        row = c.execute("SELECT * FROM bookings WHERE id=%s FOR UPDATE", (key,)).fetchone()
        if not row or row["status"] not in allowed[target]:
            raise ValueError(f"Booking cannot transition to {target}")
        if target == "completed" and (row.get("departure_at") or row["service_at"]) > datetime.now(timezone.utc):
            raise ValueError("Service time has not arrived")
        c.execute("UPDATE bookings SET status=%s,updated_at=now() WHERE id=%s", (target, key))
        if target == "completed":
            c.execute("INSERT INTO visit_events(id,booking_id,site_id,visited_at) VALUES (%s,%s,%s,now())",
                      (uuid4(), key, row["site_id"]))
    if target == "completed":
        invalidate(row["site_id"])
        try:
            sync()
        except Exception as exc:
            return {"status": target, "projection": "pending; run sync", "reason": type(exc).__name__}
    return {"status": target}


def review(key, rating, body):
    with sql() as c:
        row = c.execute("SELECT * FROM bookings WHERE id=%s", (key,)).fetchone()
        if not row or row["status"] != "completed":
            raise ValueError("Complete the visit before reviewing")
        c.execute("INSERT INTO reviews(id,booking_id,site_id,guide_id,rating,body) VALUES (%s,%s,%s,%s,%s,%s)",
                  (uuid4(), key, row["site_id"], row["guide_id"], rating, body))
    invalidate(row["site_id"])
    return {"rating": rating}


def site(key):
    key = str(key)
    stored = cached("get", page_key(key))
    if stored:
        return dict(json.loads(stored), cache_status="hit")
    version = cached("get", page_key(key)+":version") or "0"
    profile = one("sites", key)
    nearby = cypher("""MATCH (s:Site {id:$id}) OPTIONAL MATCH (s)-[:NEAR]-(n:Site)
                       RETURN s.id AS id, collect(DISTINCT n{.id,.name}) AS nearby""", id=key)
    if not nearby:
        raise ValueError("Site missing from graph")
    with sql() as c:
        stats = c.execute("""SELECT (SELECT count(*) FROM visit_events WHERE site_id=%s) AS visits,
                         avg(rating)::float AS mean_rating FROM reviews WHERE site_id=%s""", (key,key)).fetchone()
        reviews = c.execute("""SELECT rating,body,created_at FROM reviews WHERE site_id=%s
                        ORDER BY rating DESC, created_at DESC,id LIMIT 5""", (key,)).fetchall()
    result = {"MongoDB": {"site": profile, "tours": list(docs.tours.find({"site_ids":key})),
                          "guesthouses": list(docs.guesthouses.find({"site_id":key}))},
              "Neo4j": {"nearby": nearby[0]["nearby"],
                        "guides": cypher(source("neo4j/coverage.cypher"), id=key)},
              "PostgreSQL": {"stats": stats, "reviews": reviews}}
    saved = cached("eval", source("redis/store.lua"), 2, page_key(key), page_key(key)+":version",
                   version, json.dumps(result, default=str, ensure_ascii=False))
    return dict(result, cache_status="miss" if saved else "bypass")


def edit_site(key, description):
    if not description.strip() or not docs.sites.update_one(
        {"_id": key}, {"$set": {"description_ar": description}}).matched_count:
        raise ValueError("Site or description missing")
    invalidate(key)
    return {"updated": key}


def listings(key):
    cache_key = f"listing:{key}"
    stored = cached("get", cache_key)
    if stored:
        return {"cache_status": "hit", "tours": json.loads(stored)}
    one("sites", key)
    tours = list(docs.tours.find({"site_ids": key}).sort("price_ils", 1))
    saved = cached("set", cache_key, json.dumps(tours, ensure_ascii=False), ex=60)
    return {"cache_status": "miss" if saved else "bypass", "tours": tours}


def session(visitor):
    with sql() as c:
        if not c.execute("SELECT 1 FROM visitors WHERE id=%s", (visitor,)).fetchone():
            raise ValueError("Unknown visitor")
    token = secrets.token_urlsafe(24)
    cache.set("session:"+token, visitor, ex=1200)
    return {"session": token, "ttl_seconds": 1200}


def analytics():
    queries = {
        "monthly": source("postgres/analytics.sql"),
        "most_visited": "SELECT site_id,count(*) AS visits FROM visit_events GROUP BY 1 ORDER BY 2 DESC,1",
        "busiest_weekdays": "SELECT extract(isodow FROM visited_at AT TIME ZONE 'UTC') AS weekday,count(*) AS visits FROM visit_events GROUP BY 1 ORDER BY 2 DESC,1",
        "peak_quarters": "SELECT extract(quarter FROM visited_at AT TIME ZONE 'UTC') AS quarter,count(*) AS visits FROM visit_events GROUP BY 1 ORDER BY 2 DESC,1",
        "guide_ratings": "SELECT guide_id,round(avg(rating),2) AS rating FROM reviews WHERE guide_id IS NOT NULL GROUP BY 1 ORDER BY 2 DESC,1",
        "site_ratings": "SELECT site_id,round(avg(rating),2) AS rating FROM reviews GROUP BY 1 ORDER BY 2 DESC,1",
    }
    with sql() as c:
        return {name: c.execute(query).fetchall() for name, query in queries.items()}


def search(city, tag, language):
    return list(docs.sites.aggregate([
        {"$match": {"city_id": city, "tags": tag, "languages": language}},
        {"$lookup": {"from": "tours", "localField": "_id", "foreignField": "site_ids", "as": "offers"}},
        {"$project": {"name_ar": 1, "tours": {"$size": "$offers"}}}, {"$sort": {"tours": -1, "_id": 1}}
    ]))
