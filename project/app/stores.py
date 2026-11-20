import os
from pathlib import Path
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row
from pymongo import MongoClient
from neo4j import GraphDatabase
from redis import Redis
from redis.exceptions import RedisError

ROOT = Path(__file__).resolve().parents[1]


def source(name):
    return (ROOT / "db" / name).read_text(encoding="utf-8")


@contextmanager
def sql():
    with psycopg.connect(connect_timeout=4, row_factory=dict_row) as conn:
        yield conn


docs = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"),
                   serverSelectionTimeoutMS=3500).heritage
password = os.getenv("GRAPH_PASSWORD")
graph = GraphDatabase.driver(os.getenv("GRAPH_URI", "bolt://localhost:7687"),
                             auth=("neo4j", password) if password else None,
                             connection_timeout=4, max_transaction_retry_time=4)
cache = Redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379"),
                       decode_responses=True, socket_connect_timeout=1, socket_timeout=1)


def cypher(query, **params):
    with graph.session(database="neo4j") as session:
        return session.run(query, params).data()


def cached(action, *args, **kwargs):
    try:
        return getattr(cache, action)(*args, **kwargs)
    except RedisError:
        return None


def page_key(site):
    return f"site:{site}:page"


def invalidate(site):
    cached("eval", source("redis/invalidate.lua"), 2, page_key(site), page_key(site)+":version")
