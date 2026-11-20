SELECT v.site_id, to_char(v.visited_at AT TIME ZONE 'UTC','YYYY-MM') AS month,
 count(*) AS visits, round(avg(r.rating),2) AS mean_rating,
 round(avg(extract(epoch FROM v.visited_at-b.requested_at)/86400),2) AS lead_days
FROM visit_events v JOIN bookings b ON b.id=v.booking_id
LEFT JOIN reviews r ON r.booking_id=b.id
GROUP BY 1,2 ORDER BY visits DESC,month,site_id;
