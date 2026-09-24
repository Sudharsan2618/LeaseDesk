-- Integrity rules enforced in the DB, not only the app (docs/07 §5).

-- 1) Four-eyes: an APPROVE cannot be recorded by the offer's creator.
CREATE OR REPLACE FUNCTION trg_reviews_four_eyes() RETURNS trigger AS $$
DECLARE creator uuid;
BEGIN
  IF NEW.decision = 'APPROVE' THEN
    SELECT created_by INTO creator FROM offers WHERE id = NEW.offer_id;
    IF creator = NEW.reviewer_id THEN
      RAISE EXCEPTION 'four-eyes violation: creator % cannot approve own offer %', creator, NEW.offer_id;
    END IF;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS reviews_four_eyes ON reviews;
CREATE TRIGGER reviews_four_eyes BEFORE INSERT ON reviews
  FOR EACH ROW EXECUTE FUNCTION trg_reviews_four_eyes();

-- 2) touch updated_at on every offer UPDATE.
--    NOTE: the earlier "stale-result invalidation" trigger was REMOVED. With the LangGraph
--    hybrid model there is a single projection writer (repository.upsert_offer) that always
--    persists a fully-consistent state snapshot (contexts + freshly-computed results together),
--    so a DB-level guard that nulls results on context change would wrongly wipe results written
--    in the same UPDATE. Result invalidation is now the graph's responsibility: nodes recompute
--    before persisting. (See docs/06 §5 and app/graph/nodes.py.)
CREATE OR REPLACE FUNCTION trg_offers_touch_updated_at() RETURNS trigger AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS offers_invalidate_results ON offers;
DROP TRIGGER IF EXISTS offers_touch_updated_at ON offers;
CREATE TRIGGER offers_touch_updated_at BEFORE UPDATE ON offers
  FOR EACH ROW EXECUTE FUNCTION trg_offers_touch_updated_at();

-- 3) Append-only audit: block UPDATE/DELETE on audit_events.
CREATE OR REPLACE FUNCTION trg_audit_append_only() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'audit_events is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS audit_no_update ON audit_events;
CREATE TRIGGER audit_no_update BEFORE UPDATE OR DELETE ON audit_events
  FOR EACH ROW EXECUTE FUNCTION trg_audit_append_only();

-- 4) Policy pin: policy_version cannot change after creation.
CREATE OR REPLACE FUNCTION trg_offers_policy_pin() RETURNS trigger AS $$
BEGIN
  IF NEW.policy_version IS DISTINCT FROM OLD.policy_version THEN
    RAISE EXCEPTION 'policy_version is immutable (was %, tried %)', OLD.policy_version, NEW.policy_version;
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS offers_policy_pin ON offers;
CREATE TRIGGER offers_policy_pin BEFORE UPDATE ON offers
  FOR EACH ROW EXECUTE FUNCTION trg_offers_policy_pin();
