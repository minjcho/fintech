-- ==========================================
-- Azure MySQL Connection Pool Check Script
-- ==========================================
-- Purpose: Verify that Azure MySQL can handle the required connection pool size
--
-- How to run:
-- 1. Connect to Azure MySQL:
--    mysql -h <server>.mysql.database.azure.com -u <username>@<server> -p
--
-- 2. Run this script:
--    source scripts/check_mysql_connections.sql
--
-- 3. Or run individual queries:
--    mysql -h <server> -u <username> -p < scripts/check_mysql_connections.sql

-- Check current max_connections limit
SELECT
    @@max_connections AS max_connections,
    @@max_connections - 10 AS available_for_app,
    CASE
        WHEN @@max_connections >= 240 THEN '✅ Sufficient for 4 workers'
        WHEN @@max_connections >= 120 THEN '⚠️  Sufficient for 2 workers only'
        ELSE '❌ Insufficient - upgrade required'
    END AS status
;

-- Check current active connections
SELECT
    COUNT(*) AS current_connections,
    @@max_connections AS max_allowed,
    ROUND((COUNT(*) / @@max_connections) * 100, 2) AS usage_percentage
FROM information_schema.processlist
;

-- Show connection details by user
SELECT
    user,
    host,
    COUNT(*) AS connection_count
FROM information_schema.processlist
GROUP BY user, host
ORDER BY connection_count DESC
;

-- Calculate required connections for analysis service
SELECT
    'Analysis Service Requirements' AS service,
    4 AS uvicorn_workers,
    20 AS pool_size_per_worker,
    40 AS max_overflow_per_worker,
    (20 + 40) * 4 AS total_connections_needed,
    @@max_connections AS mysql_max_connections,
    CASE
        WHEN @@max_connections >= (20 + 40) * 4 THEN '✅ OK'
        ELSE '❌ Need upgrade'
    END AS verdict
;

-- ==========================================
-- If max_connections is insufficient:
-- ==========================================
-- Option 1: Reduce pool size (modify .env)
--   UVICORN_WORKERS=2
--   This will auto-adjust pool_size to 10 and max_overflow to 20
--   Total: 2 * (10 + 20) = 60 connections

-- Option 2: Upgrade Azure MySQL tier
--   az mysql server update \
--     --resource-group <resource-group> \
--     --name <server-name> \
--     --sku-name <sku> \
--     --tier <tier>

-- Common Azure MySQL tiers and max_connections:
-- - Basic B1:      50 connections
-- - Basic B2:      100 connections
-- - General Purpose GP_Gen5_2:  300 connections
-- - General Purpose GP_Gen5_4:  625 connections
-- - General Purpose GP_Gen5_8:  1250 connections

-- ==========================================
-- Test connection pool settings
-- ==========================================
-- After deployment, monitor active connections:
-- Run this query every 5 minutes for 1 hour during peak load

SELECT
    NOW() AS check_time,
    COUNT(*) AS active_connections,
    @@max_connections AS max_allowed,
    ROUND((COUNT(*) / @@max_connections) * 100, 2) AS usage_pct,
    CASE
        WHEN COUNT(*) / @@max_connections > 0.9 THEN '❌ CRITICAL - Near limit'
        WHEN COUNT(*) / @@max_connections > 0.7 THEN '⚠️  WARNING - High usage'
        ELSE '✅ OK'
    END AS status
FROM information_schema.processlist
;
