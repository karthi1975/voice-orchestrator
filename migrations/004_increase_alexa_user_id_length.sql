-- Migration: Increase alexa_user_id column length
-- Date: 2026-02-03
-- Purpose: Amazon user IDs can exceed 255 characters, increase to 500

-- Increase column size to accommodate long Alexa user IDs
ALTER TABLE alexa_user_mappings
ALTER COLUMN alexa_user_id TYPE VARCHAR(500);

-- Update Karthi's mapping with real Alexa user ID
-- Replace this with your actual Alexa user ID from the logs
UPDATE alexa_user_mappings
SET alexa_user_id = 'amzn1.ask.account.AMAVH7ILO5KNECI2JWFDFN6KNYVQ3M3ISFHLHMAKU5WYFXUDSU4KDRCJQFQSKCHYQDPVXRYFSZUHTTTWFO2X4L2MDQGYZVYWORTI4I6ISQ7ZPMGOBGAQ5HGV4BAYGYNWKATAOJXKVLGUPYEQ4ITQH25MG4A2EPZE2PCGEZPBCFT3OGWSYABIINEM3TTA3RHC65UD2TYHI34WS45ZQRQYCWOVB5HEHMFA6EFKZNUZONGA'
WHERE home_id = 'karthi_test_home';

-- Verify the update
SELECT alexa_user_id, home_id, created_at FROM alexa_user_mappings;
