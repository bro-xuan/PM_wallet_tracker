# MongoDB Connection Troubleshooting

## Issue Identified

The poller is experiencing MongoDB connection timeouts with DNS resolution errors:

```
[poller] MongoDB connection timeout - check network/MongoDB URI: 
getaddrinfo ENOTFOUND ac-iplvzmm-shard-00-0 1.3a92ryv.mongodb.net
```

**Key Observations**:
1. Error shows hostname: `ac-iplvzmm-shard-00-0.1.3a92ryv.mongodb.net`
2. Current connection string uses: `polymarketdata.3a92ryv.mongodb.net`
3. Direct connection test works fine (1.01s)
4. Poller is failing to connect

## Root Cause Analysis

### Possible Causes:

1. **Cached Connection**: Next.js dev server may have cached an old MongoDB connection string
2. **Connection Pool**: MongoDB driver may be trying to connect to a shard that's no longer valid
3. **Replica Set Configuration**: The connection string might be resolving to old replica set members
4. **Environment Variable**: Different connection string being used at runtime vs. what's in `.env.local`

## Solutions

### Solution 1: Restart Next.js Dev Server

The most common cause is a cached connection. Restart the dev server:

```bash
# Stop the current server (Ctrl+C)
# Then restart:
npm run dev
```

This will:
- Clear any cached MongoDB connections
- Reload environment variables
- Establish fresh connections

### Solution 2: Verify MongoDB Atlas Connection String

1. Go to MongoDB Atlas dashboard
2. Check your cluster connection string
3. Ensure it matches what's in `.env.local`
4. Verify IP whitelist includes your current IP
5. Check if cluster is running (not paused)

### Solution 3: Update Connection String Format

If using a replica set, ensure the connection string includes all shards or uses SRV format:

**SRV Format (Recommended)**:
```
mongodb+srv://username:password@cluster.mongodb.net/database?retryWrites=true&w=majority
```

**Standard Format**:
```
mongodb://username:password@host1:port1,host2:port2/database?replicaSet=rs0
```

### Solution 4: Add Connection Retry Logic

The poller should handle connection failures gracefully. Current implementation:
- Catches errors and logs them
- Returns empty array/empty result on failure
- Continues polling (doesn't crash)

**Improvement**: Add exponential backoff for retries

### Solution 5: Check Network/Firewall

1. Verify your IP is whitelisted in MongoDB Atlas
2. Check if VPN/proxy is interfering
3. Test connection from different network
4. Verify DNS resolution works: `nslookup ac-iplvzmm-shard-00-0.1.3a92ryv.mongodb.net`

## Current Error Handling

The poller already has error handling:
- `wallets()`: Returns empty array on error
- `getCursor()`: Returns 0 on error
- `updateCursor()`: Logs error, continues
- `upsertTrade()`: Returns false on error

**This means**: The poller continues running even with connection errors, but operations fail silently.

## Recommended Actions

1. **Immediate**: Restart Next.js dev server
2. **Verify**: Check MongoDB Atlas connection string matches `.env.local`
3. **Test**: Run direct connection test (already done - works fine)
4. **Monitor**: Watch logs after restart to see if errors persist

## Long-term Improvements

1. Add connection retry logic with exponential backoff
2. Add health check endpoint to monitor MongoDB connection
3. Add metrics/logging for connection failures
4. Consider connection pooling improvements

