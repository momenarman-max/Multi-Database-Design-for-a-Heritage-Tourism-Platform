-- A single snapshot of both keys: name, value size in bytes and remaining TTL.
local rows = {}
for _, key in ipairs(KEYS) do
  rows[#rows + 1] = {key, redis.call('STRLEN', key), redis.call('TTL', key)}
end
return rows
