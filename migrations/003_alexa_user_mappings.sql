-- Migration: Add Alexa User to Home mappings table
-- Date: 2026-02-02
-- Purpose: Map Alexa user IDs to home IDs for multi-tenant support

-- Create alexa_user_mappings table
CREATE TABLE IF NOT EXISTS alexa_user_mappings (
    alexa_user_id VARCHAR(255) PRIMARY KEY,
    home_id VARCHAR(255) NOT NULL REFERENCES homes(home_id) ON DELETE CASCADE,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

-- Create index for faster lookups
CREATE INDEX IF NOT EXISTS idx_alexa_mappings_home_id ON alexa_user_mappings(home_id);

-- Insert mappings for Karthi and Becca
-- Note: Replace these Alexa user IDs with real ones from your Alexa account

-- Karthi's mapping (test user ID - update with real ID)
INSERT INTO alexa_user_mappings (alexa_user_id, home_id, created_at)
VALUES ('amzn1.ask.account.KARTHI_TEST', 'karthi_test_home', CURRENT_TIMESTAMP)
ON CONFLICT (alexa_user_id) DO UPDATE SET
    home_id = EXCLUDED.home_id,
    updated_at = CURRENT_TIMESTAMP;

-- Becca's mapping (update with real Alexa user ID)
-- Get real user ID from: Session -> User -> userId in Alexa request JSON
-- Example: amzn1.ask.account.AEHFJK...
INSERT INTO alexa_user_mappings (alexa_user_id, home_id, created_at)
VALUES ('amzn1.ask.account.BECCA', 'becca_farewell_beach', CURRENT_TIMESTAMP)
ON CONFLICT (alexa_user_id) DO UPDATE SET
    home_id = EXCLUDED.home_id,
    updated_at = CURRENT_TIMESTAMP;

-- Verify insertions
SELECT * FROM alexa_user_mappings;
