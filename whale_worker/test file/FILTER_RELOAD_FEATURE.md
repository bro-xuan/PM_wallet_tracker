# Dynamic Filter Reload Feature

## Problem
Previously, user filters were loaded only once at worker startup. When users changed their filter settings and clicked "Save Settings", those changes wouldn't take effect until the worker was restarted.

## Solution
Implemented automatic filter reloading that refreshes user filters periodically during the worker's polling loop.

## Implementation

### Configuration
Added `FILTER_RELOAD_INTERVAL_SECONDS` environment variable (default: 60 seconds):
- Configurable via `.env.local`: `FILTER_RELOAD_INTERVAL_SECONDS=60`
- Defaults to 60 seconds if not set
- Filters are reloaded automatically every N seconds

### Changes Made

1. **`whale_worker/config.py`**:
   - Added `FILTER_RELOAD_INTERVAL_SECONDS` configuration option

2. **`whale_worker/main.py`**:
   - Added filter reload tracking (`last_filter_reload` timestamp)
   - Added periodic filter reload check in the main polling loop
   - Reloads filters when the interval has elapsed
   - Logs filter changes (count differences)
   - Gracefully handles reload errors (uses cached filters)

### How It Works

1. **Startup**: Filters are loaded once at startup (as before)
2. **During Polling**: Every poll cycle checks if `FILTER_RELOAD_INTERVAL_SECONDS` has elapsed
3. **Reload**: If interval elapsed, fetches fresh filters from MongoDB
4. **Update**: Replaces the in-memory filter list with the new one
5. **Logging**: Reports if filter count changed or if reload failed

### Example Output

```
📊 Poll #15 - Fetching trades...
   🔄 Reloading user filters (checking for updates)...
   ✅ Filters refreshed: 3 active filters (no changes)

📊 Poll #16 - Fetching trades...
   🔄 Reloading user filters (checking for updates)...
   ✅ Filters updated: 3 → 4 active filters
```

### Benefits

- ✅ **No Restart Required**: Filter changes take effect within 60 seconds (configurable)
- ✅ **Efficient**: Only reloads when interval elapsed, not on every poll
- ✅ **Resilient**: Continues using cached filters if reload fails
- ✅ **Observable**: Logs when filters are reloaded and if they changed
- ✅ **Configurable**: Can adjust reload interval via environment variable

### Configuration

Add to `.env.local`:
```bash
# Reload user filters every 60 seconds (default)
FILTER_RELOAD_INTERVAL_SECONDS=60

# Or reload more frequently (e.g., every 30 seconds)
FILTER_RELOAD_INTERVAL_SECONDS=30

# Or less frequently (e.g., every 5 minutes)
FILTER_RELOAD_INTERVAL_SECONDS=300
```

### Performance Considerations

- **Database Query**: Each reload queries MongoDB for enabled configs and active Telegram accounts
- **Frequency**: Default 60 seconds balances responsiveness with database load
- **Caching**: Filters are cached in memory between reloads
- **Error Handling**: If reload fails, worker continues with previously loaded filters

### Testing

To test the feature:
1. Start the worker
2. Note the number of active filters in the startup log
3. Change a user's filter settings via the web UI
4. Click "Save Settings"
5. Wait up to `FILTER_RELOAD_INTERVAL_SECONDS` seconds
6. Check worker logs for filter reload message
7. Verify new trades are matched against updated filters

