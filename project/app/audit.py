from stores import cypher, docs, sql


def audit():
    problems = []
    def check(ok, label):
        if not ok:
            problems.append(label)

    keys = {c: set(docs[c].distinct("_id")) for c in ("sites","guides","tours","guesthouses")}
    for label, collection in [("Site","sites"),("Guide","guides"),("Provider","guesthouses")]:
        ids = {r["id"] for r in cypher(f"MATCH (n:{label}) RETURN n.id AS id")}
        check(ids == keys[collection], f"{label} and {collection} IDs differ")
    for s in docs.sites.find():
        dst = cypher("MATCH (:Site {id:$s})-[:LOCATED_IN]->(c:City) RETURN c.id AS id", s=s["_id"])
        check({r["id"] for r in dst} == {s["city_id"]}, "city for "+s["_id"])
    for t in docs.tours.find():
        check(bool(t["site_ids"]) and set(t["site_ids"]) <= keys["sites"], "tour site "+t["_id"])
        check(t["guide_id"] in keys["guides"], "tour guide "+t["_id"])
        covers = cypher("MATCH (:Guide {id:$g})-[:COVERS]->(s:Site) RETURN s.id AS id", g=t["guide_id"])
        check(set(t["site_ids"]) <= {r["id"] for r in covers}, "guide coverage "+t["_id"])
    for h in docs.guesthouses.find():
        check(h["site_id"] in keys["sites"], "guesthouse site "+h["_id"])
    with sql() as c:
        visitors = {str(r["id"]) for r in c.execute("SELECT id FROM visitors")}
        check(visitors == {r["id"] for r in cypher("MATCH (v:Visitor) RETURN v.id AS id")}, "visitor IDs differ")
        for b in c.execute("SELECT * FROM bookings"):
            check(str(b["offering_id"]) in keys[b["offering_type"]], "booking offer "+str(b["id"]))
            check(str(b["site_id"]) in keys["sites"], "booking site "+str(b["id"]))
        events = c.execute("""SELECT DISTINCT b.visitor_id,e.site_id FROM visit_events e
                              JOIN bookings b ON b.id=e.booking_id""")
        pairs = {(str(r["visitor_id"]), str(r["site_id"])) for r in events}
        projected = cypher("MATCH (v:Visitor)-[:VISITED]->(s:Site) RETURN v.id AS v,s.id AS s")
        check(pairs == {(r["v"],r["s"]) for r in projected}, "VISITED projection differs")
    if problems:
        raise ValueError("Reference audit: "+" | ".join(problems))
    return {"references": "ok", "sites": len(keys["sites"])}
