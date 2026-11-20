-- Rename the logical generation even when no page exists yet.
redis.call('INCR', KEYS[2])
redis.call('EXPIRE', KEYS[2], 86400)
return redis.call('DEL', KEYS[1])
