-- psql: a disposable booking exercises CRUD inside a rolled-back transaction.
BEGIN;
INSERT INTO bookings(id,visitor_id,offering_id,offering_type,site_id,requested_at,service_at)
SELECT gen_random_uuid(),visitor_id,offering_id,offering_type,site_id,now(),now()
FROM bookings ORDER BY id LIMIT 1 RETURNING id AS scratch_id \gset
SELECT status FROM bookings WHERE id=:'scratch_id';
UPDATE bookings SET status='cancelled',updated_at=now() WHERE id=:'scratch_id' AND status='requested';
DELETE FROM bookings WHERE id=:'scratch_id' AND status='cancelled';
ROLLBACK;
EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM visit_events
WHERE site_id='00000000-0000-0000-0000-0000001e8481' ORDER BY visited_at DESC LIMIT 5;
