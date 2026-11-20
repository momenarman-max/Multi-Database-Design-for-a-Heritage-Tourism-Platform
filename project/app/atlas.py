"""Trusted local operator console for Heritage Atlas."""
import argparse
import json
import sys
from uuid import UUID

import service
from audit import audit
from sample import KINDS, uid
from seed import seed
from stores import cache, cypher, source, sql


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="command", required=True)

    def command(name, fn, *fields):
        sub = commands.add_parser(name)
        for field in fields:
            sub.add_argument(field)
        sub.set_defaults(run=fn)
        return sub

    command("seed", seed)
    command("sync", service.sync)
    command("audit", audit)
    command("analytics", service.analytics)
    command("site", service.site, "key")
    command("edit-site", service.edit_site, "key", "description")
    command("listing", service.listings, "key")
    command("session", service.session, "visitor")
    command("session-check", lambda token: {"visitor": cache.get("session:"+token),
            "ttl": cache.ttl("session:"+token)}, "token")
    command("logout", lambda token: cache.delete("session:"+token), "token")
    command("cache-info", lambda key: cache.eval(source("redis/inspect.lua"), 2,
            service.page_key(key), "listing:"+key), "key")
    command("recommend", lambda key: cypher(source("neo4j/recommend.cypher"), id=key), "key")
    command("search", service.search, "city", "tag", "language")
    register = command("register", service.register, "name", "email")
    register.add_argument("--interests", nargs="+", default=[])
    register.add_argument("--languages", nargs="+", default=["ar"])
    request = command("request-booking", service.request, "visitor", "kind", "offering")
    request.add_argument("--at")
    for verb, target in [("confirm","confirmed"),("complete","completed"),("cancel","cancelled")]:
        command(verb+"-booking", lambda key, t=target: service.transition(key,t), "key")
    command("add-review", lambda key,rating,body: service.review(key,int(rating),body), "key","rating","body")
    def booking(key):
        with sql() as c:
            row = c.execute("SELECT * FROM bookings WHERE id=%s",(key,)).fetchone()
            if not row:
                raise ValueError("Unknown booking")
            return row
    command("booking", booking, "key")
    def sample_id(kind, number):
        if kind not in KINDS or int(number) < 1:
            raise ValueError("Unknown sample ID")
        return uid(kind,int(number))
    command("id", sample_id, "kind", "number")
    args = vars(p.parse_args())
    fn = args.pop("run")
    args.pop("command")
    return fn(**args)


if __name__ == "__main__":
    try:
        print(json.dumps(main(), ensure_ascii=False, indent=2, default=str))
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        sys.exit(1)
