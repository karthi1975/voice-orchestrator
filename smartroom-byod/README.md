# Smartroom BYOD lane — implementation

Additive only. The nine shipped functions and the iPad contract are untouched;
these three new functions deploy as their own codebase (`byod`), so even a full
`firebase deploy` from this directory can never modify or delete the shipped ones.

## Pieces

| Piece | Kind | What it does |
|---|---|---|
| `joinRoom` | new fn (roomJoins create) | Validates `{uid, roomNo, code}` against the room's current join code; mints `subscriptions/{uid}_smartroom` with `role:"byod"`, `boundUid`, `expiresAt:+7d`. Flips the join doc to `joined`/`rejected`. |
| `byodJanitor` | new fn (every 10 min) | Mints a `joinCode` (+`joinCodeUid`) onto every bound `rooms/{roomNo}`; purges BYOD subs that are **orphaned** (room doc gone, or `room.uid != boundUid` after a rebind) or **expired**. |
| `byodTokenSweep` | new fn (daily 03:30 Denver) | Silent FCM ping; a sub whose every token is UNREGISTERED (app uninstalled) is purged; partial deaths prune the token array. |
| `roomJoins` rules block | rules addition | Create-own-pending / read-own, anonymous provider required — same shape as `roomRegistrations`. No existing rule changed. |

**Why no shipped-code edits are needed:** the shipped `purgeRoom()` deletes
`rooms/{roomNo}` and a rebind rewrites it via `set()` with the new uid. Every
BYOD sub records `boundUid` at join time, so `byodJanitor` sees any ended stay
within one 10-min tick and cascades the purge to the phones (subs + inboxes +
anon Auth users). The join code is keyed to the binding (`joinCodeUid`), so a
new stay automatically gets a fresh code — old QR photos/PINs die.

Cascade latencies: rebind/admin erase → ≤10 min for phones; heartbeat janitor
(still 72 h until the iPad's 5-min retune ships) → +≤10 min after room purge;
uninstall → ~1–2 days; expiry → 7 days.

## Deploy (needs fresh auth)

```sh
# 1) rules: add the roomJoins block to the live ruleset (REST; see deploy-rules.sh)
# 2) functions:
cd smartroom-byod
export PATH="$PWD/../firebase-emulator/tools/node/bin:$PATH"
../firebase-emulator/tools/node_modules/.bin/firebase deploy \
  --only functions:joinRoom,functions:byodJanitor,functions:byodTokenSweep \
  --project smarthomeadapt-broadcast --non-interactive
```

## Deliberately NOT done (iPad impact / separate steps)

1. **Janitor retune (72 h → 30 min)** — only after Aaron ships the 5-min
   heartbeat build; retuning first would purge a daily-beating iPad.
2. **Subscription-rule hardening** — today any anonymous user can still
   self-create a smartroom subscription (pre-existing rule gap), so the join
   code is a UX gate, not yet a security gate. The fix (allow client
   create/update of a smartroom sub only when
   `get(/rooms/$(rooms[0])).data.uid == request.auth.uid`, i.e. only the bound
   iPad; BYOD subs come from `joinRoom` via Admin SDK which bypasses rules) is
   iPad-safe but should ship together with restoring the strict ruleset.
3. **iPad QR/PIN display** — additive client work: read `rooms/{roomNo}.joinCode`
   (already readable by the bound device) and render `SMARTROOM|{roomNo}|{code}`
   as QR + the code as text.

## Client

`client/SmartroomByodJoin.cs` — join-screen template for Aaron (scan/type →
anonymous sign-in → `roomJoins` doc → verdict listener → inbox + session-end
listeners). Messages reuse the existing inbox model unchanged.
