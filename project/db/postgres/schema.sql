CREATE TABLE IF NOT EXISTS visitors (
 id uuid PRIMARY KEY, name text NOT NULL, email text UNIQUE NOT NULL,
 interests text[] NOT NULL, languages text[] NOT NULL
);
CREATE TABLE IF NOT EXISTS bookings (
 id uuid PRIMARY KEY, visitor_id uuid NOT NULL REFERENCES visitors,
 offering_id uuid NOT NULL, offering_type text NOT NULL CHECK(offering_type IN ('tours','guesthouses')),
 site_id uuid NOT NULL, guide_id uuid, status text NOT NULL DEFAULT 'requested'
 CHECK(status IN ('requested','confirmed','completed','cancelled')),
 requested_at timestamptz NOT NULL DEFAULT now(), service_at timestamptz NOT NULL,
 updated_at timestamptz NOT NULL DEFAULT now(), CHECK(service_at >= requested_at)
);
CREATE TABLE IF NOT EXISTS visit_events (
 id uuid PRIMARY KEY, booking_id uuid NOT NULL UNIQUE REFERENCES bookings,
 site_id uuid NOT NULL, visited_at timestamptz NOT NULL, projected boolean NOT NULL DEFAULT false
);
CREATE TABLE IF NOT EXISTS reviews (
 id uuid PRIMARY KEY, booking_id uuid NOT NULL UNIQUE REFERENCES bookings, site_id uuid NOT NULL,
 guide_id uuid, rating smallint NOT NULL CHECK(rating BETWEEN 1 AND 5),
 body text NOT NULL CHECK(length(trim(body))>0), created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS bookings_visitor_status ON bookings(visitor_id,status);
CREATE INDEX IF NOT EXISTS bookings_service ON bookings(service_at);
CREATE INDEX IF NOT EXISTS reviews_site ON reviews(site_id);
CREATE INDEX IF NOT EXISTS visits_site_time ON visit_events(site_id,visited_at);
CREATE OR REPLACE FUNCTION validate_review() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
 IF NOT EXISTS (SELECT FROM bookings WHERE id=NEW.booking_id AND status='completed'
 AND site_id=NEW.site_id AND guide_id IS NOT DISTINCT FROM NEW.guide_id) THEN
 RAISE EXCEPTION 'Review requires a completed matching booking'; END IF;
 RETURN NEW;
END $$;
CREATE OR REPLACE TRIGGER review_eligibility BEFORE INSERT OR UPDATE ON reviews
FOR EACH ROW EXECUTE FUNCTION validate_review();
CREATE TABLE IF NOT EXISTS web_credentials (
 visitor_id uuid PRIMARY KEY REFERENCES visitors(id) ON DELETE CASCADE,
 salt bytea NOT NULL, verifier bytea NOT NULL
);
ALTER TABLE bookings ADD COLUMN IF NOT EXISTS departure_at timestamptz
 CHECK (departure_at IS NULL OR (offering_type='guesthouses' AND departure_at>service_at));
