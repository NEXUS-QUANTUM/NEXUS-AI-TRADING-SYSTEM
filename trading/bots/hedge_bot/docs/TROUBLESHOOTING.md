# NEXUS Hedge Bot Troubleshooting Guide
Version: 2.0.0
Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved


## Table of Contents

1. [Overview](#overview)
2. [Common Issues](#common-issues)
3. [Configuration Issues](#configuration-issues)
4. [Connection Issues](#connection-issues)
5. [Trading Issues](#trading-issues)
6. [Performance Issues](#performance-issues)
7. [Database Issues](#database-issues)
8. [API Issues](#api-issues)
9. [WebSocket Issues](#websocket-issues)
10. [Security Issues](#security-issues)
11. [Error Codes](#error-codes)
12. [Debugging Tools](#debugging-tools)
13. [Log Analysis](#log-analysis)
14. [Recovery Procedures](#recovery-procedures)
15. [Performance Tuning](#performance-tuning)
16. [Support](#support)

---

## Overview

This guide provides comprehensive troubleshooting information for the NEXUS Hedge Bot. It covers common issues, their causes, and step-by-step solutions.

### Troubleshooting Framework

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      TROUBLESHOOTING FRAMEWORK                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. IDENTIFY                                                                 │
│     └── Recognize the issue and its symptoms                                │
│                                                                             │
│  2. DIAGNOSE                                                                 │
│     └── Determine the root cause using logs and metrics                     │
│                                                                             │
│  3. RESOLVE                                                                  │
│     └── Apply the appropriate fix                                           │
│                                                                             │
│  4. VERIFY                                                                   │
│     └── Confirm the issue is resolved                                       │
│                                                                             │
│  5. PREVENT                                                                  │
│     └── Implement measures to prevent recurrence                            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Common Issues

### Quick Reference

| Issue | Symptoms | Likely Cause | Resolution |
|-------|----------|--------------|------------|
| Bot not starting | Process exits immediately | Configuration error | Check config files |
| No trades executed | Zero positions | Strategy not activated | Enable strategy |
| API errors | 401/403 responses | Invalid credentials | Check API keys |
| High latency | Slow response times | Resource exhaustion | Scale resources |
| Memory leaks | Increasing memory usage | Unclosed connections | Restart service |
| Database errors | Connection failures | Connection pool exhausted | Increase pool size |

---

## Configuration Issues

### Configuration Not Loading

**Symptoms:**
- Bot starts with default configuration
- Custom settings not applied
- Environment variables ignored

**Diagnosis:**
```bash
# Check configuration files
ls -la /opt/nexus-trading/config/
cat /opt/nexus-trading/config/default_config.yaml

# Check environment variables
env | grep NEXUS

# Verify configuration loading
tail -f /var/log/nexus-trading/hedge_bot.log | grep "Configuration"
```

**Resolution:**
```bash
# Ensure configuration directory exists
mkdir -p /opt/nexus-trading/config

# Copy default configuration
cp /opt/nexus-trading/config/default_config.yaml /opt/nexus-trading/config/default_config.yaml.bak
cp examples/config/default_config.yaml /opt/nexus-trading/config/

# Set correct permissions
chmod 644 /opt/nexus-trading/config/*.yaml

# Reload configuration
curl -X POST http://localhost:8000/config/reload
```

### Invalid Configuration Values

**Symptoms:**
- Validation errors in logs
- Bot crashes on startup
- Unexpected behavior

**Diagnosis:**
```bash
# Check configuration validation
python -c "from trading.bots.hedge_bot.config import validate_config; print(validate_config())"

# Check specific configuration section
python -c "from trading.bots.hedge_bot.config import get_config; print(get_config().bot)"
```

**Resolution:**
```yaml
# Example: Fix invalid environment
bot:
  environment: "production"  # Correct value

# Example: Fix invalid exchange
exchange:
  name: "binance"  # Correct value

# Example: Fix invalid leverage
trading:
  position:
    max_leverage: 3.0  # Must be between 1.0 and 10.0
```

---

## Connection Issues

### Exchange API Connection

**Symptoms:**
- `ConnectionError` in logs
- Orders fail to execute
- Price data not updating

**Diagnosis:**
```bash
# Test exchange connection
python scripts/test_exchange.py

# Check exchange API status
curl -X GET http://localhost:8000/exchange/status

# Check network connectivity
ping api.binance.com
curl -I https://api.binance.com/api/v3/ping
```

**Resolution:**
```bash
# Check API keys
echo $NEXUS_EXCHANGE_API_KEY
echo $NEXUS_EXCHANGE_API_SECRET

# Verify API key permissions
python scripts/verify_api_keys.py

# Reset rate limits
redis-cli DEL "rate_limit:exchange"

# Restart exchange connection
curl -X POST http://localhost:8000/exchange/reconnect
```

### Database Connection

**Symptoms:**
- `DatabaseError` in logs
- Slow query performance
- Data inconsistency

**Diagnosis:**
```bash
# Check database status
psql -h localhost -U nexus -d nexus_trading -c "SELECT 1"

# Check connection pool
psql -h localhost -U nexus -d nexus_trading -c "SELECT count(*) FROM pg_stat_activity;"

# Check database logs
tail -f /var/log/postgresql/postgresql.log
```

**Resolution:**
```bash
# Increase connection pool
# In docker-compose.yml or Kubernetes values.yaml
environment:
  - NEXUS_DATABASE_POOL_SIZE=20

# Restart database connection
curl -X POST http://localhost:8000/database/reconnect

# Reset connection pool
python scripts/reset_db_pool.py
```

### Redis Connection

**Symptoms:**
- `RedisError` in logs
- Cache misses
- Pub/sub failures

**Diagnosis:**
```bash
# Check Redis status
redis-cli ping

# Check Redis memory
redis-cli info memory

# Check Redis connections
redis-cli info clients
```

**Resolution:**
```bash
# Clear Redis cache
redis-cli FLUSHALL

# Restart Redis
docker-compose restart redis

# Increase Redis memory
# In redis.conf or docker-compose.yml
redis:
  command: redis-server --maxmemory 1gb --maxmemory-policy allkeys-lru
```

---

## Trading Issues

### Orders Not Executing

**Symptoms:**
- Orders stuck in pending state
- No fills after long period
- Order cancellation fails

**Diagnosis:**
```bash
# Check order status
curl -X GET http://localhost:8000/trading/orders

# Check order book
curl -X GET http://localhost:8000/trading/orderbook/BTCUSDT

# Check market depth
python scripts/check_market_depth.py BTCUSDT
```

**Resolution:**
```python
# Example: Cancel stuck orders
async def cancel_stuck_orders():
    orders = await get_pending_orders()
    for order in orders:
        if order.age > 300:  # 5 minutes
            await cancel_order(order.id)
            logger.info(f"Cancelled stuck order: {order.id}")

# Example: Adjust order price
async def adjust_order_price(order: Order, new_price: float):
    await cancel_order(order.id)
    new_order = Order(
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        price=new_price,
        type=OrderType.LIMIT
    )
    await place_order(new_order)
```

### Position Management Issues

**Symptoms:**
- Incorrect position sizes
- Unrealized PnL calculation errors
- Hedging not working

**Diagnosis:**
```bash
# Check positions
curl -X GET http://localhost:8000/trading/positions

# Check position details
curl -X GET http://localhost:8000/trading/positions/{position_id}

# Check hedging status
curl -X GET http://localhost:8000/strategy/status
```

**Resolution:**
```bash
# Force position sync
curl -X POST http://localhost:8000/trading/sync-positions

# Recalculate PnL
curl -X POST http://localhost:8000/trading/recalculate-pnl

# Reset hedging
curl -X POST http://localhost:8000/strategy/reset-hedging
```

### Strategy Execution Issues

**Symptoms:**
- Strategy not generating signals
- Incorrect hedge ratios
- Rebalancing not occurring

**Diagnosis:**
```bash
# Check strategy status
curl -X GET http://localhost:8000/strategy/status

# Check strategy logs
tail -f /var/log/nexus-trading/strategy.log

# Check strategy metrics
curl -X GET http://localhost:8000/strategy/metrics
```

**Resolution:**
```bash
# Restart strategy
curl -X POST http://localhost:8000/strategy/restart

# Update strategy parameters
curl -X PATCH http://localhost:8000/strategy/parameters \
  -H "Content-Type: application/json" \
  -d '{"hedge_ratio": 0.55}'

# Force rebalance
curl -X POST http://localhost:8000/strategy/rebalance
```

---

## Performance Issues

### High Latency

**Symptoms:**
- Slow API responses
- Delayed order execution
- UI lag

**Diagnosis:**
```bash
# Check API latency
curl -w "@curl-format.txt" -o /dev/null -s http://localhost:8000/health

# Check system resources
top
htop
docker stats

# Check database performance
psql -h localhost -U nexus -d nexus_trading -c "SELECT pg_stat_statements_reset();"
psql -h localhost -U nexus -d nexus_trading -c "SELECT query, calls, total_time, mean_time FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"
```

**Resolution:**
```yaml
# Increase worker count
performance:
  max_workers: 20

# Enable caching
performance:
  use_caching: true
  cache_ttl: 60

# Optimize database indexes
CREATE INDEX CONCURRENTLY idx_trades_timestamp ON trades(timestamp);
CREATE INDEX CONCURRENTLY idx_positions_symbol ON positions(symbol);
```

### Memory Issues

**Symptoms:**
- Out of memory errors
- High swap usage
- Process crashes

**Diagnosis:**
```bash
# Check memory usage
free -h
docker stats
kubectl top pods

# Check memory leaks
python -c "import tracemalloc; tracemalloc.start(); # ..."

# Analyze heap
python -c "import pympler; pympler.summary.summarize(pympler.muppy.get_objects())"
```

**Resolution:**
```yaml
# Increase memory limit
performance:
  resources:
    max_memory_mb: 4096

# Enable garbage collection
performance:
  garbage_collection: true
  gc_interval: 60

# Reduce cache size
performance:
  cache_size: 1000
```

---

## Database Issues

### Slow Queries

**Symptoms:**
- API timeouts
- Dashboard load delays
- Database CPU high

**Diagnosis:**
```sql
-- Find slow queries
SELECT query, calls, total_time, mean_time 
FROM pg_stat_statements 
ORDER BY mean_time DESC 
LIMIT 10;

-- Check locks
SELECT pid, usename, query, state, wait_event 
FROM pg_stat_activity 
WHERE state != 'idle';

-- Check table sizes
SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) 
FROM pg_tables 
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC 
LIMIT 10;
```

**Resolution:**
```sql
-- Create indexes
CREATE INDEX CONCURRENTLY idx_trades_symbol_timestamp ON trades(symbol, timestamp);
CREATE INDEX CONCURRENTLY idx_market_data_symbol_timestamp ON market_data(symbol, timestamp);

-- Vacuum analyze
VACUUM ANALYZE trades;
VACUUM ANALYZE market_data;
VACUUM ANALYZE positions;

-- Partition tables
SELECT create_hypertable('trades', 'timestamp', chunk_time_interval => interval '7 days');
```

### Connection Pool Exhaustion

**Symptoms:**
- "Too many clients" errors
- Connection timeouts
- API failures

**Diagnosis:**
```sql
-- Check connections
SELECT count(*) FROM pg_stat_activity;

-- Check connection limits
SHOW max_connections;
```

**Resolution:**
```bash
# Increase max connections
# In postgresql.conf
max_connections = 200

# In docker-compose.yml
environment:
  - POSTGRES_MAX_CONNECTIONS=200

# Increase pool size
environment:
  - NEXUS_DATABASE_POOL_SIZE=30
```

---

## API Issues

### Authentication Issues

**Symptoms:**
- 401 Unauthorized responses
- Token expired errors
- Login failures

**Diagnosis:**
```bash
# Check token validity
curl -X GET http://localhost:8000/auth/verify \
  -H "Authorization: Bearer $TOKEN"

# Check token expiration
python -c "import jwt; print(jwt.decode('$TOKEN', options={'verify_signature': False}))"
```

**Resolution:**
```bash
# Refresh token
curl -X POST http://localhost:8000/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\": \"$REFRESH_TOKEN\"}"

# Reset API keys
curl -X POST http://localhost:8000/auth/reset-keys \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Rate Limiting Issues

**Symptoms:**
- 429 Too Many Requests
- Throttled responses
- Delayed processing

**Diagnosis:**
```bash
# Check rate limit headers
curl -I http://localhost:8000/api/endpoint

# Check current rate limits
redis-cli GET "rate_limit:client_id"
```

**Resolution:**
```yaml
# Increase rate limits
security:
  api:
    rate_limiting: true
    max_requests_per_minute: 120

# Clear rate limits
redis-cli DEL "rate_limit:*"
```

---

## WebSocket Issues

### Connection Failures

**Symptoms:**
- WebSocket connection errors
- No real-time updates
- Frequent disconnections

**Diagnosis:**
```bash
# Test WebSocket connection
wscat -c ws://localhost:8080/ws

# Check WebSocket logs
tail -f /var/log/nexus-trading/websocket.log

# Check connection count
curl -X GET http://localhost:8000/websocket/status
```

**Resolution:**
```bash
# Increase connection limit
websocket:
  max_connections: 1000

# Enable keepalive
websocket:
  keepalive_interval: 30

# Restart WebSocket service
docker-compose restart websocket
```

### Message Delivery Issues

**Symptoms:**
- Missing updates
- Delayed messages
- Duplicate messages

**Diagnosis:**
```bash
# Check message queue
redis-cli LLEN websocket:messages

# Check subscriber count
redis-cli PUBSUB NUMSUB websocket:updates

# Check message latency
python scripts/check_websocket_latency.py
```

**Resolution:**
```bash
# Clear message queue
redis-cli DEL websocket:messages

# Reset subscriptions
redis-cli PUBSUB NUMPAT

# Restart message broker
docker-compose restart redis
```

---

## Security Issues

### Authentication Bypass

**Symptoms:**
- Unauthorized access attempts
- Suspicious API calls
- Unknown IPs in logs

**Diagnosis:**
```bash
# Check access logs
tail -f /var/log/nexus-trading/access.log

# Check failed login attempts
grep "Login failed" /var/log/nexus-trading/auth.log

# Check suspicious activity
python scripts/analyze_security_logs.py
```

**Resolution:**
```yaml
# Enable IP whitelisting
security:
  api:
    ip_whitelist:
      - "192.168.1.0/24"
      - "10.0.0.0/8"

# Enable rate limiting
security:
  api:
    rate_limiting: true
    max_requests_per_minute: 60

# Enable MFA
security:
  auth:
    multi_factor_auth: true
```

### Data Breach

**Symptoms:**
- Unusual data access
- Modified logs
- Unauthorized configuration changes

**Diagnosis:**
```bash
# Check audit logs
tail -f /var/log/nexus-trading/audit.log

# Check configuration changes
grep "Configuration changed" /var/log/nexus-trading/hedge_bot.log

# Check data access
python scripts/audit_data_access.py
```

**Resolution:**
```bash
# Rotate API keys
curl -X POST http://localhost:8000/auth/rotate-keys \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Revoke all sessions
curl -X POST http://localhost:8000/auth/revoke-all \
  -H "Authorization: Bearer $ADMIN_TOKEN"

# Enable encryption
security:
  encryption: true
  encryption_method: "AES-256-GCM"
```

---

## Error Codes

### API Error Codes

| Code | Description | Solution |
|------|-------------|----------|
| `AUTH_001` | Invalid credentials | Check username/password |
| `AUTH_002` | Token expired | Refresh token |
| `AUTH_003` | Insufficient permissions | Check user roles |
| `CONF_001` | Configuration error | Validate config file |
| `CONF_002` | Invalid configuration value | Fix config values |
| `DB_001` | Database connection failed | Check database status |
| `DB_002` | Query timeout | Optimize query or increase timeout |
| `EXCH_001` | Exchange API error | Check API keys and connectivity |
| `EXCH_002` | Rate limit exceeded | Reduce request rate |
| `TRD_001` | Insufficient balance | Add funds |
| `TRD_002` | Order rejected | Check order parameters |
| `TRD_003` | Position limit exceeded | Reduce position size |
| `RISK_001` | Risk limit exceeded | Reduce exposure |
| `RISK_002` | Drawdown limit reached | Stop trading |
| `WS_001` | WebSocket connection failed | Check WebSocket service |
| `WS_002` | Subscription failed | Check subscription parameters |

### Log Error Patterns

```python
# Common error patterns and their solutions
error_patterns = {
    "ConnectionRefusedError": "Check service is running and port is accessible",
    "TimeoutError": "Increase timeout or check network latency",
    "KeyError": "Check configuration for missing keys",
    "ValueError": "Check data types and ranges",
    "DatabaseError": "Check database connection and query syntax",
    "APIError": "Check API endpoint and authentication",
    "AuthenticationError": "Check credentials and token validity",
    "RateLimitError": "Reduce request frequency or increase limit",
}
```

---

## Debugging Tools

### Logging

```yaml
# Enable debug logging
logging:
  config:
    log_level: "DEBUG"
    log_format: "json"

# Enable verbose logging
logging:
  categories:
    debug: true
    trace: true

# Enable audit logging
logging:
  categories:
    audit: true
```

### Profiling

```python
# Enable performance profiling
async def profile_function(func):
    import cProfile
    import pstats
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    result = await func()
    
    profiler.disable()
    stats = pstats.Stats(profiler).sort_stats('cumtime')
    stats.print_stats(20)
    
    return result

# Enable memory profiling
from pympler import summary, muppy

def profile_memory():
    all_objects = muppy.get_objects()
    sum1 = summary.summarize(all_objects)
    summary.print_(sum1)
```

### Health Checks

```bash
# Check service health
curl -X GET http://localhost:8000/health

# Check service readiness
curl -X GET http://localhost:8000/ready

# Check service liveness
curl -X GET http://localhost:8000/live

# Check metrics
curl -X GET http://localhost:8000/metrics
```

---

## Log Analysis

### Key Log Files

| Log File | Purpose | Location |
|----------|---------|----------|
| `hedge_bot.log` | Main application log | `/var/log/nexus-trading/` |
| `trades.log` | Trade execution log | `/var/log/nexus-trading/` |
| `errors.log` | Error log | `/var/log/nexus-trading/` |
| `audit.log` | Audit trail | `/var/log/nexus-trading/` |
| `performance.log` | Performance metrics | `/var/log/nexus-trading/` |
| `websocket.log` | WebSocket events | `/var/log/nexus-trading/` |
| `access.log` | API access log | `/var/log/nexus-trading/` |

### Log Analysis Commands

```bash
# Find errors
grep ERROR /var/log/nexus-trading/hedge_bot.log

# Find specific error pattern
grep "ConnectionError" /var/log/nexus-trading/hedge_bot.log

# Analyze error frequency
grep ERROR /var/log/nexus-trading/hedge_bot.log | cut -d' ' -f1-3 | sort | uniq -c

# View recent logs
tail -f /var/log/nexus-trading/hedge_bot.log

# Search logs by time range
sed -n '/2026-07-30 10:00/,/2026-07-30 11:00/p' /var/log/nexus-trading/hedge_bot.log
```

---

## Recovery Procedures

### Emergency Stop

```bash
# Emergency stop all trading
curl -X POST http://localhost:8000/emergency/stop

# Close all positions
curl -X POST http://localhost:8000/emergency/close-all

# Stop all strategies
curl -X POST http://localhost:8000/emergency/stop-strategies
```

### Data Recovery

```bash
# Restore from backup
python scripts/restore_backup.py --backup /backups/nexus/backup_20260730.sql

# Rebuild database
python scripts/rebuild_db.py

# Restore configuration
cp /backups/nexus/config_backup.tar.gz /opt/nexus-trading/config/
tar -xzf /opt/nexus-trading/config/config_backup.tar.gz
```

### System Recovery

```bash
# Restart all services
docker-compose restart

# Rebuild containers
docker-compose up -d --build

# Reset to last known good state
python scripts/reset_system.py --state stable

# Recover from crash
python scripts/recover_system.py
```

---

## Performance Tuning

### Database Tuning

```sql
-- PostgreSQL performance tuning
ALTER SYSTEM SET shared_buffers = '512MB';
ALTER SYSTEM SET effective_cache_size = '2GB';
ALTER SYSTEM SET work_mem = '16MB';
ALTER SYSTEM SET maintenance_work_mem = '128MB';
ALTER SYSTEM SET random_page_cost = 1.1;
ALTER SYSTEM SET effective_io_concurrency = 200;
ALTER SYSTEM SET wal_buffers = '16MB';
ALTER SYSTEM SET max_connections = 200;

SELECT pg_reload_conf();
```

### Application Tuning

```yaml
# Application performance tuning
performance:
  # Worker configuration
  max_workers: 20
  batch_size: 200
  queue_size: 5000

  # Caching
  use_caching: true
  cache_ttl: 60
  cache_size: 5000

  # Async configuration
  use_async: true
  max_concurrent_tasks: 50

  # Database pooling
  database_pool_size: 30
  database_pool_timeout: 30
```

---

## Support

### Getting Help

1. **Documentation**
   - https://docs.nexusquantum.com
   - Check the specific guide for your issue

2. **Logs**
   - Gather relevant logs
   - Include timestamps and error messages

3. **Metrics**
   - Check Grafana dashboards
   - Collect performance metrics

4. **Contact Support**
   - Email: support@nexusquantum.com
   - Slack: #nexus-support
   - Priority: Critical issues 24/7

### Support Request Template

```markdown
## Issue Summary
[Brief description of the issue]

## Environment
- Version: [Version number]
- Environment: [Production/Staging/Development]
- Deployment: [Docker/Kubernetes/AWS/GCP/Azure]

## Symptoms
- [List symptoms observed]

## Steps to Reproduce
1. [Step 1]
2. [Step 2]
3. [Step 3]

## Logs
[Include relevant logs]

## Metrics
[Include relevant metrics]

## Attempted Solutions
- [What you've tried]

## Additional Information
- [Any other relevant information]
```

---

## Copyright

Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

This document is proprietary and confidential. Unauthorized use, copying, or distribution is prohibited.
