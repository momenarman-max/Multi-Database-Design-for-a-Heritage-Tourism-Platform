from datetime import datetime, timedelta, timezone
from sample import CITIES, GUIDES, HOUSES, NEAR, SITES, VISITORS, catalog, uid
from stores import cypher, docs, invalidate, source, sql


def node(label, id_, name):
    cypher(f"MERGE (n:{label} {{id:$id}}) SET n.name=$name", id=id_, name=name)


def edge(left, relation, right, a, b):
    cypher(f"MATCH (a:{left} {{id:$a}}),(b:{right} {{id:$b}}) MERGE (a)-[:{relation}]->(b)", a=a, b=b)


def seed():
    from service import sync
    for collection, obj in catalog():
        docs[collection].update_one({"_id": obj["_id"]}, {"$setOnInsert": obj}, upsert=True)
    docs.sites.create_index([("city_id", 1), ("tags", 1)])
    docs.tours.create_index("site_ids")
    docs.guesthouses.create_index("site_id")
    docs.guides.create_index("languages")
    for label in ("Site", "City", "Visitor", "Guide", "Provider"):
        cypher(f"CREATE CONSTRAINT IF NOT EXISTS FOR (n:{label}) REQUIRE n.id IS UNIQUE")
    for i, name in enumerate(CITIES, 1):
        node("City", uid("city", i), name)
    for i, (name, city, _, _) in enumerate(SITES, 1):
        node("Site", uid("site", i), name)
        edge("Site", "LOCATED_IN", "City", uid("site", i), uid("city", city))
    for i, (name, sites) in enumerate(GUIDES, 1):
        node("Guide", uid("guide", i), name)
        for s in sites:
            edge("Guide", "COVERS", "Site", uid("guide", i), uid("site", s))
    for i, (name, s) in enumerate(HOUSES, 1):
        node("Provider", uid("guesthouse", i), name)
        edge("Provider", "PROVIDES", "Site", uid("guesthouse", i), uid("site", s))
    for a, b in NEAR:
        edge("Site", "NEAR", "Site", uid("site", a), uid("site", b))
    with sql() as c:
        c.execute(source("postgres/schema.sql"))
        for i, (name, interests) in enumerate(VISITORS, 1):
            c.execute("INSERT INTO visitors VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                      (uid("visitor", i), name, f"v{i}@example.invalid", interests, ["ar"]))
        # Three reviews on site 1; a fourth visit makes a recommendation possible.
        for i, (v, site, tour, guide, month, day, lead, rating) in enumerate([
            (1,1,1,1,3,5,2,5), (2,1,2,2,3,12,4,4), (3,1,1,1,4,2,5,3), (2,2,3,1,4,3,3,5)
        ], 1):
            when = datetime(2026, month, day, 10, tzinfo=timezone.utc)
            booking = uid("booking", i)
            c.execute("""INSERT INTO bookings VALUES (%s,%s,%s,'tours',%s,%s,'completed',%s,%s,%s)
                         ON CONFLICT DO NOTHING""", (booking, uid("visitor", v), uid("tour", tour),
                         uid("site", site), uid("guide", guide), when-timedelta(days=lead), when, when))
            c.execute("INSERT INTO visit_events VALUES (%s,%s,%s,%s,false) ON CONFLICT DO NOTHING",
                      (uid("event", i), booking, uid("site", site), when))
            c.execute("INSERT INTO reviews VALUES (%s,%s,%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING",
                      (uid("review", i), booking, uid("site", site), uid("guide", guide), rating,
                       ["شرح واضح للأقواس.", "أحببت الجولة في السوق.", "أحتاج وقتاً أطول للمشي.", "وقفة جميلة عند الحرفيين."][i-1], when))
    sync()
    for i in range(1, len(SITES)+1):
        invalidate(uid("site", i))
    return {"sites": len(SITES), "guides": len(GUIDES), "stays": len(HOUSES)}
