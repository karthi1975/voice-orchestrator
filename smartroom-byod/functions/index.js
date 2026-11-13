/**
 * Smartroom BYOD lane — additive Cloud Functions (2nd gen, us-west1).
 *
 * Deployed as its own codebase ("byod"); none of the nine shipped broadcast
 * functions are modified, so the wall-iPad lane cannot be impacted.
 *
 *   joinRoom        roomJoins create   → validate per-room join code, mint a
 *                                        7-day BYOD subscription
 *   byodJanitor     every 10 minutes   → keep a join code on every bound room
 *                                        (rotates automatically after purge or
 *                                        rebind), and purge BYOD subscriptions
 *                                        that are orphaned or expired
 *   byodTokenSweep  daily 03:30 Denver → silent FCM ping; a subscription whose
 *                                        every token is UNREGISTERED (app
 *                                        uninstalled) is purged
 *
 * How the cascade works WITHOUT touching the shipped purge: the shipped
 * purgeRoom() deletes rooms/{roomNo}, and a rebind rewrites it via set() with a
 * new uid. Each BYOD subscription records boundUid (the display's uid at join
 * time). byodJanitor purges any BYOD sub whose room doc is gone or whose
 * room.uid no longer equals boundUid — so rebind, admin erase, and the
 * heartbeat janitor all cascade to the phones within one 10-minute tick.
 * The join code is keyed to the binding (joinCodeUid): a new binding gets a
 * fresh code, so QR photos and PINs die with the stay.
 */

const { onDocumentCreated } = require("firebase-functions/v2/firestore");
const { onSchedule } = require("firebase-functions/v2/scheduler");
const { setGlobalOptions } = require("firebase-functions/v2");
const logger = require("firebase-functions/logger");
const admin = require("firebase-admin");
const crypto = require("crypto");

admin.initializeApp();
const db = admin.firestore();

setGlobalOptions({ region: "us-west1", maxInstances: 10 });

const BYOD_TTL_DAYS = 7;
// No confusable characters (I/L/O/0/1) — the code doubles as a typed PIN.
const CODE_CHARS = "ABCDEFGHJKMNPQRSTUVWXYZ23456789";
const CODE_LEN = 6;

const ts = () => admin.firestore.FieldValue.serverTimestamp();

function mintCode() {
  let c = "";
  for (let i = 0; i < CODE_LEN; i++) c += CODE_CHARS[crypto.randomInt(CODE_CHARS.length)];
  return c;
}

/** Erase one BYOD user: subscription(s), inbox, users doc, anonymous Auth user. */
async function purgeByodUser(uid) {
  const writer = db.bulkWriter();
  const subs = await db.collection("subscriptions").where("uid", "==", uid).get();
  subs.forEach((d) => writer.delete(d.ref));
  const inbox = await db.collection(`users/${uid}/inbox`).get();
  inbox.forEach((d) => writer.delete(d.ref));
  writer.delete(db.doc(`users/${uid}`));
  await writer.close();
  await admin.auth().deleteUser(uid).catch(() => {}); // may already be gone
}

// ─────────────────────────────────────────────────────────────────────────────
// joinRoom — a relative's phone (anonymous auth) writes /roomJoins
// { uid, roomNo, code, status: "pending" }. Validates the room's current join
// code and creates the time-boxed subscription. Mirrors registerRoom's shape.
// Re-joining with a current code renews the 7-day expiry.
// ─────────────────────────────────────────────────────────────────────────────
exports.joinRoom = onDocumentCreated("roomJoins/{id}", async (event) => {
  const snap = event.data;
  if (!snap) return;
  const { uid, roomNo, code, status, deviceTokens } = snap.data();
  if (status !== "pending") return; // idempotency guard
  const fail = (reason) =>
    snap.ref.update({ status: "rejected", reason, processedAt: ts() });

  if (!uid || !roomNo || !code) return fail("uid, roomNo and code are required");

  const reg = await db.doc(`roomRegistry/${roomNo}`).get();
  if (!reg.exists || reg.get("active") !== true) return fail(`unknown or inactive room '${roomNo}'`);

  const room = await db.doc(`rooms/${roomNo}`).get();
  if (!room.exists) return fail("room has no active display");
  if (uid === room.get("uid")) return fail("the room display registers; it does not join");

  const current = room.get("joinCode");
  if (!current || String(code).trim().toUpperCase() !== current) return fail("invalid join code");

  const expiresAt = admin.firestore.Timestamp.fromMillis(
    Date.now() + BYOD_TTL_DAYS * 24 * 3600 * 1000
  );
  await db.doc(`subscriptions/${uid}_smartroom`).set({
    uid,
    communityId: "smartroom",
    active: true,
    rooms: [roomNo],
    role: "byod",
    boundUid: room.get("uid"), // the stay this join belongs to
    deviceTokens: Array.isArray(deviceTokens) ? deviceTokens.slice(0, 5) : [],
    joinedAt: ts(),
    expiresAt,
  });
  await snap.ref.update({ status: "joined", expiresAt, processedAt: ts() });
  logger.info("byod joined", { roomNo, uid });
});

// ─────────────────────────────────────────────────────────────────────────────
// byodJanitor — every 10 minutes.
// 1) Every bound room carries a join code tied to its current binding. A purge
//    deletes rooms/{roomNo}; a rebind rewrites it without joinCode — either
//    way the next tick mints a fresh code.
// 2) BYOD subs whose stay ended (room gone or rebound) or whose expiresAt
//    passed are purged. The bound display's own uid is never touched.
// ─────────────────────────────────────────────────────────────────────────────
exports.byodJanitor = onSchedule({ schedule: "every 10 minutes" }, async () => {
  const rooms = await db.collection("rooms").get();
  const byNo = new Map();
  let minted = 0;
  for (const d of rooms.docs) {
    let data = d.data();
    if (!data.joinCode || data.joinCodeUid !== data.uid) {
      const joinCode = mintCode();
      await d.ref.set({ joinCode, joinCodeUid: data.uid, joinCodeMintedAt: ts() }, { merge: true });
      data = { ...data, joinCode, joinCodeUid: data.uid };
      minted++;
      logger.info("join code minted", { roomNo: d.id });
    }
    byNo.set(d.id, data);
  }

  const subs = await db.collection("subscriptions").where("role", "==", "byod").get();
  let purged = 0;
  const now = Date.now();
  for (const d of subs.docs) {
    const s = d.data();
    if (s.communityId !== "smartroom") continue;
    const room = byNo.get((s.rooms || [])[0]);
    if (room && s.uid === room.uid) continue; // safety: never the bound display
    const orphaned = !room || room.uid !== s.boundUid; // stay ended: purge or rebind
    const expired = s.expiresAt && s.expiresAt.toMillis() < now;
    if (!orphaned && !expired) continue;
    await purgeByodUser(s.uid);
    purged++;
    logger.info("byod purged", { subId: d.id, orphaned, expired: !!expired });
  }
  logger.info("byodJanitor done", { rooms: rooms.size, byodSubs: subs.size, minted, purged });
});

// ─────────────────────────────────────────────────────────────────────────────
// byodTokenSweep — daily. Uninstall detector: FCM marks a token UNREGISTERED
// once the app is gone. A silent data-only ping surfaces that; a sub whose
// every token is dead is purged, partial deaths just prune the array.
// Subs with no tokens are left to the expiry/orphan sweeps.
// ─────────────────────────────────────────────────────────────────────────────
exports.byodTokenSweep = onSchedule(
  { schedule: "every day 03:30", timeZone: "America/Denver" },
  async () => {
    const subs = await db.collection("subscriptions").where("role", "==", "byod").get();
    let purged = 0;
    let pruned = 0;
    for (const d of subs.docs) {
      const tokens = d.get("deviceTokens") || [];
      if (!tokens.length) continue;
      const res = await admin.messaging().sendEachForMulticast({
        tokens,
        data: { type: "ping" },
        android: { priority: "normal" },
        apns: { headers: { "apns-priority": "5" }, payload: { aps: { "content-available": 1 } } },
      });
      const dead = tokens.filter(
        (t, i) => res.responses[i].error?.code === "messaging/registration-token-not-registered"
      );
      if (dead.length === tokens.length) {
        await purgeByodUser(d.get("uid"));
        purged++;
      } else if (dead.length) {
        await d.ref.update({ deviceTokens: admin.firestore.FieldValue.arrayRemove(...dead) });
        pruned += dead.length;
      }
    }
    logger.info("byodTokenSweep done", { subs: subs.size, purged, pruned });
  }
);
