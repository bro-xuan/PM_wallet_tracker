# User Isolation Test Plan

## Test Objective
Verify that:
1. User `zhixuan_wang@outlook.de` sees all previously added wallets (migrated from SQLite)
2. Other users see NO wallets and must build from scratch
3. Each user's data is completely isolated

## Test Steps

### Prerequisites
- Dev server running: `npm run dev`
- MongoDB connected
- SQLite has some wallets (from before migration)

### Test 1: Login as zhixuan_wang@outlook.de

1. **Navigate to app**
   ```
   http://localhost:3000/app
   ```

2. **Login**
   - Click "Login" button
   - Enter email: `zhixuan_wang@outlook.de`
   - Enter password
   - Click "Login"

3. **Verify Wallets Panel**
   - Check "Watch wallets" panel on the left
   - ✅ **Expected**: Should see all previously added wallets from SQLite
   - ✅ **Expected**: Wallets should appear automatically (auto-migrated)

4. **Verify Trades Panel**
   - Check "Live trades" panel on the right
   - ✅ **Expected**: Should see trades from those wallets
   - ✅ **Expected**: Trade count should match the number of trades for those wallets

### Test 2: Logout and Login as Different User

1. **Logout**
   - Click "Logout" button
   - ✅ **Expected**: Should redirect or show login screen
   - ✅ **Expected**: All data should disappear

2. **Register New User**
   - Click "Login" → "Register" tab
   - Enter email: `testuser@example.com`
   - Enter password (min 6 chars)
   - Confirm password
   - Click "Register"
   - ✅ **Expected**: Should receive OTP email
   - Enter OTP code
   - Click "Verify Email"
   - ✅ **Expected**: Should auto-login after verification

3. **Verify Empty State**
   - Check "Watch wallets" panel
   - ✅ **Expected**: Should see NO wallets (empty list)
   - ✅ **Expected**: Should see message or empty state
   
4. **Verify No Trades**
   - Check "Live trades" panel
   - ✅ **Expected**: Should see NO trades
   - ✅ **Expected**: Table should be empty or show "No trades" message

### Test 3: Add Wallet as New User

1. **Add Wallet**
   - In "Watch wallets" panel, enter a wallet address
   - Click "Add"
   - ✅ **Expected**: Wallet should appear in the list
   - ✅ **Expected**: Should only see trades for this wallet

2. **Verify Isolation**
   - Logout
   - Login as `zhixuan_wang@outlook.de` again
   - ✅ **Expected**: Should NOT see the wallet added by testuser@example.com
   - ✅ **Expected**: Should only see zhixuan_wang@outlook.de's wallets

### Test 4: API-Level Verification

You can also test via API calls (requires session cookies):

```bash
# Test 1: Get wallets as zhixuan_wang@outlook.de
# (Requires login session cookie)
curl http://localhost:3000/api/wallets

# Expected: Returns array of wallet addresses for that user

# Test 2: Get trades as zhixuan_wang@outlook.de  
curl http://localhost:3000/api/trades/recent

# Expected: Returns trades filtered by user's wallets only

# Test 3: Try to access without auth
curl http://localhost:3000/api/wallets

# Expected: {"error":"Unauthorized"} with 401 status
```

## Expected Results Summary

| User | Wallets Visible | Trades Visible | Can Add Wallets |
|------|----------------|----------------|-----------------|
| zhixuan_wang@outlook.de | ✅ All migrated wallets | ✅ Trades from those wallets | ✅ Yes |
| testuser@example.com | ❌ None (empty) | ❌ None (empty) | ✅ Yes (starts fresh) |
| Not logged in | ❌ None | ❌ None | ❌ No (must login) |

## Success Criteria

✅ **Test Passes If:**
- zhixuan_wang@outlook.de sees all previously added wallets
- New users see empty wallets list
- Each user can only see their own wallets
- Each user can only see trades from their own wallets
- Unauthenticated users see login prompt
- Data is completely isolated between users

❌ **Test Fails If:**
- New users see wallets from other users
- zhixuan_wang@outlook.de doesn't see migrated wallets
- Trades are visible to wrong users
- Unauthenticated users can see any data

