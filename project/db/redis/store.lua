-- A writer may have invalidated this page while a reader assembled it.
if (redis.call('GET', KEYS[2]) or '0') ~= ARGV[1] then return 0 end
return redis.call('SET', KEYS[1], ARGV[2], 'EX', 90)
