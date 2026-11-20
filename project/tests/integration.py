"""Run against a seeded classroom database. Fixtures are removed after each test."""
import sys
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from psycopg import errors
from redis import Redis
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import service
import stores
from audit import audit
from seed import seed
from sample import uid

SITE = uid("site", 1)


class Integration(unittest.TestCase):
    def visitor(self):
        key = service.register("Test visitor", f"{uuid4()}@example.invalid", ["test"], ["ar"])
        self.addCleanup(self.remove_visitor, key)
        return key

    @staticmethod
    def remove_visitor(key):
        with stores.sql() as c:
            for table in ("reviews","visit_events"):
                c.execute(f"DELETE FROM {table} WHERE booking_id IN (SELECT id FROM bookings WHERE visitor_id=%s)", (key,))
            c.execute("DELETE FROM bookings WHERE visitor_id=%s", (key,))
            c.execute("DELETE FROM visitors WHERE id=%s", (key,))
        stores.cypher("MATCH (v:Visitor {id:$id}) DETACH DELETE v", id=key)
        stores.invalidate(SITE)

    def test_page_and_invalidation(self):
        stores.invalidate(SITE)
        first = service.site(SITE)
        self.assertEqual(first["cache_status"], "miss")
        self.assertEqual(len(first["MongoDB"]["tours"]), 2)
        self.assertEqual(len(first["Neo4j"]["nearby"]), 2)
        self.assertEqual(len(first["PostgreSQL"]["reviews"]), 3)
        self.assertEqual(service.site(SITE)["cache_status"], "hit")
        original = first["MongoDB"]["site"]["description_ar"]
        self.addCleanup(service.edit_site, SITE, original)
        service.edit_site(SITE, "وصف مؤقت للاختبار")
        fresh = service.site(SITE)
        self.assertEqual((fresh["cache_status"],fresh["MongoDB"]["site"]["description_ar"]), ("miss","وصف مؤقت للاختبار"))

    def test_booking_lifecycle(self):
        v = self.visitor()
        b = service.request(v, "tours", uid("tour",1))
        with self.assertRaises(ValueError):
            service.review(b,4,"Too early")
        with self.assertRaises(ValueError):
            service.transition(b,"completed")
        service.transition(b,"confirmed")
        before = service.site(SITE)["PostgreSQL"]["stats"]["visits"]
        service.transition(b,"completed")
        page = service.site(SITE)
        self.assertEqual((page["cache_status"],page["PostgreSQL"]["stats"]["visits"]), ("miss",before+1))
        with self.assertRaises(ValueError):
            service.transition(b,"completed")
        with self.assertRaises(errors.CheckViolation):
            service.review(b,9,"Invalid rating")
        service.review(b,5,"Integration check")
        self.assertEqual(service.site(SITE)["cache_status"],"miss")
        with self.assertRaises(errors.UniqueViolation):
            service.review(b,4,"Duplicate")
        self.assertEqual(service.sync()["visits_projected"],0)
        self.assertEqual(audit()["references"],"ok")

    def test_cancel_stay_and_invalid_offer(self):
        v = self.visitor()
        with self.assertRaises(ValueError):
            service.request(v,"guesthouses",str(uuid4()))
        b = service.request(v,"guesthouses",uid("guesthouse",1))
        service.transition(b,"cancelled")
        with self.assertRaises(ValueError):
            service.transition(b,"completed")
        with self.assertRaises(ValueError):
            service.review(b,3,"Cancelled")

    def test_analytics(self):
        data = service.analytics()
        rows = {r["month"]: r for r in data["monthly"] if str(r["site_id"]) == SITE}
        self.assertEqual((rows["2026-03"]["visits"],float(rows["2026-03"]["mean_rating"]),
                          float(rows["2026-03"]["lead_days"])), (2,4.5,3))
        self.assertEqual(float(rows["2026-04"]["lead_days"]),5)
        with stores.sql() as c:
            top = c.execute("SELECT count(*) AS n FROM visit_events GROUP BY site_id ORDER BY n DESC LIMIT 1").fetchone()
        self.assertEqual(data["most_visited"][0]["visits"],top["n"])
        self.assertEqual(int(data["busiest_weekdays"][0]["weekday"]),4)
        self.assertEqual(float(data["site_ratings"][-1]["rating"]),4)

    def test_graph_and_document_queries(self):
        guides = stores.cypher(stores.source("neo4j/coverage.cypher"), id=SITE)
        self.assertEqual([(r["id"],r["covered"]) for r in guides], [(uid("guide",2),3),(uid("guide",1),2)])
        results = stores.cypher(stores.source("neo4j/recommend.cypher"), id=uid("visitor",1))
        self.assertEqual([r["id"] for r in results],[uid("site",2)])
        self.assertEqual(stores.cypher(stores.source("neo4j/recommend.cypher"),id=uid("visitor",2)),[])
        matches = service.search(uid("city",1),"عمارة","ar")
        self.assertEqual([(r["_id"],r["tours"]) for r in matches], [(SITE,2),(uid("site",3),0)])

    def test_missing_reference(self):
        key = str(uuid4())
        stores.docs.tours.insert_one({"_id":key,"site_ids":[key],"guide_id":uid("guide",1)})
        self.addCleanup(stores.docs.tours.delete_one, {"_id":key})
        with self.assertRaisesRegex(ValueError,"tour site"):
            audit()

    def test_redis_outage(self):
        expected = service.site(SITE)["PostgreSQL"]["stats"]
        offline = Redis(host="127.0.0.1", port=1, socket_connect_timeout=.2)
        with patch.object(stores,"cache",offline):
            result = service.site(SITE)
        self.assertEqual(result["cache_status"], "bypass")
        self.assertEqual(result["PostgreSQL"]["stats"],expected)

    def test_required_database_outage(self):
        client = MongoClient("mongodb://127.0.0.1:1",serverSelectionTimeoutMS=200)
        self.addCleanup(client.close)
        key = str(uuid4())
        with patch.object(service,"docs",client.heritage), self.assertRaises(ServerSelectionTimeoutError):
            service.site(key)
        self.assertIsNone(stores.cache.get(stores.page_key(key)))

    def test_sessions_and_listing(self):
        token = service.session(uid("visitor",1))["session"]
        key = "session:"+token
        self.addCleanup(stores.cache.delete,key)
        self.assertEqual(stores.cache.get(key),uid("visitor",1))
        self.assertTrue(0 < stores.cache.ttl(key) <= 1200)
        stores.cache.delete("listing:"+SITE)
        self.assertEqual(service.listings(SITE)["cache_status"],"miss")
        self.assertEqual(service.listings(SITE)["cache_status"],"hit")
        values = stores.cache.eval(stores.source("redis/inspect.lua"),2,stores.page_key(SITE),"listing:"+SITE)
        self.assertGreater(values[1][1],0)

    def test_reseed_preserves_counts(self):
        before = service.site(SITE)["PostgreSQL"]["stats"]["visits"]
        seed()
        self.assertEqual(audit()["sites"],9)
        self.assertEqual(service.site(SITE)["PostgreSQL"]["stats"]["visits"],before)


if __name__ == "__main__":
    unittest.main(verbosity=2)


