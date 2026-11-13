/**
 * SmartHome Broadcast Message Service — Cloud Functions (2nd gen, us-west1)
 *
 * Principle: the Firestore inbox is the source of truth; FCM is only a doorbell.
 * Every broadcast is written to each subscriber's inbox first; push is best-effort.
 *
 * Flow:
 *   composeBroadcast (admin) → writes 1 /broadcasts doc
 *      → onBroadcastCreated (trigger) resolves audience, chunks into Cloud Tasks
 *         → fanoutChunk (task) writes inbox docs + sends FCM
 *   onSubscriptionChange keeps FCM community topics in sync on opt-in/out
 *   trimInboxes (nightly) caps each inbox at 100
 */

const { onCall, HttpsError } = require("firebase-functions/v2/https");
const { onDocumentCreated, onDocumentWritten } = require("firebase-functions/v2/firestore");
const { onTaskDispatched } = require("firebase-functions/v2/tasks");
const { onSchedule } = require("firebase-functions/v2/scheduler");
const { setGlobalOptions } = require("firebase-functions/v2");
const logger = require("firebase-functions/logger");
const admin = require("firebase-admin");
const { getFunctions } = require("firebase-admin/functions");

admin.initializeApp();
const db = admin.firestore();

setGlobalOptions({ region: "us-west1", maxInstances: 20 });

// Recipients per Cloud Tasks payload. Kept small to stay well under the task
// size limit and the FCM 500-token multicast cap.
const CHUNK_SIZE = 100;
const INBOX_CAP = 100;

// ─────────────────────────────────────────────────────────────────────────────
// B5.1  composeBroadcast — admin-only. Validates, writes ONE broadcast doc.
// ─────────────────────────────────────────────────────────────────────────────
exports.composeBroadcast = onCall(async (request) => {
  if (!request.auth || request.auth.token.admin !== true) {
    throw new HttpsError("permission-denied", "Admin only.");
  }
  const { communityId, targetRoomIds = [], title, body } = request.data || {};
  if (!communityId || !title || !body) {
    throw new HttpsError("invalid-argument", "communityId, title, and body are required.");
  }

  const commSnap = await db.doc(`communities/${communityId}`).get();
  if (!commSnap.exists || commSnap.get("active") !== true) {
    throw new HttpsError("failed-precondition", `Community '${communityId}' not found or inactive.`);
  }

  const ref = db.collection("broadcasts").doc();
  await ref.set({
    communityId,
    targetRoomIds,
    title,
    body,
    sentBy: request.auth.token.email || request.auth.uid,
    sentAt: admin.firestore.FieldValue.serverTimestamp(),
    status: "queued",
  });

  logger.info("composeBroadcast queued", { broadcastId: ref.id, communityId, targetRoomIds });
  return { broadcastId: ref.id };
});

// ─────────────────────────────────────────────────────────────────────────────
// B5.2  onBroadcastCreated — resolve audience, chunk, enqueue Cloud Tasks.
// ─────────────────────────────────────────────────────────────────────────────
exports.onBroadcastCreated = onDocumentCreated("broadcasts/{broadcastId}", async (event) => {
  const snap = event.data;
  if (!snap) return;
  const broadcast = snap.data();
  const broadcastId = event.params.broadcastId;
  if (broadcast.status !== "queued") return; // idempotency guard

  // Active subscriptions for this community (uses the composite index).
  const subsSnap = await db
    .collection("subscriptions")
    .where("communityId", "==", broadcast.communityId)
    .where("active", "==", true)
    .get();

  const targetRooms = broadcast.targetRoomIds || [];
  const recipients = [];
  subsSnap.forEach((doc) => {
    const s = doc.data();
    if (targetRooms.length > 0) {
      const subRooms = s.rooms || [];
      if (!subRooms.some((r) => targetRooms.includes(r))) return; // room-targeted: skip non-matches
    }
    recipients.push({ uid: s.uid, tokens: s.deviceTokens || [] });
  });

  const chunks = [];
  for (let i = 0; i < recipients.length; i += CHUNK_SIZE) {
    chunks.push(recipients.slice(i, i + CHUNK_SIZE));
  }

  logger.info("fan-out dispatching", { broadcastId, recipients: recipients.length, chunks: chunks.length });

  const queue = getFunctions().taskQueue("locations/us-west1/functions/fanoutChunk");
  await Promise.all(
    chunks.map((chunk) =>
      queue.enqueue(
        { broadcastId, title: broadcast.title, body: broadcast.body, communityId: broadcast.communityId, recipients: chunk },
        { dispatchDeadlineSeconds: 300 }
      )
    )
  );

  await snap.ref.update({ status: "dispatched", audienceCount: recipients.length, chunkCount: chunks.length });
});

// ─────────────────────────────────────────────────────────────────────────────
// B5.3  fanoutChunk — write inbox docs (truth), then send FCM (best-effort).
// ─────────────────────────────────────────────────────────────────────────────
exports.fanoutChunk = onTaskDispatched(
  { retryConfig: { maxAttempts: 5, minBackoffSeconds: 5 }, rateLimits: { maxConcurrentDispatches: 10 } },
  async (req) => {
    const { broadcastId, title, body, communityId, recipients } = req.data;

    // 1) Inbox writes — idempotent per (uid, broadcastId), so retries are safe.
    const writer = db.bulkWriter();
    for (const r of recipients) {
      writer.set(
        db.doc(`users/${r.uid}/inbox/${broadcastId}`),
        {
          broadcastId,
          communityId,
          title,
          body,
          sentAt: admin.firestore.FieldValue.serverTimestamp(),
          read: false,
          readAt: null,
        },
        { merge: true }
      );
    }
    await writer.close();

    // 2) Push doorbell — carry title/body for the lock screen.
    const tokens = recipients.flatMap((r) => r.tokens || []);
    for (let i = 0; i < tokens.length; i += 500) {
      const batch = tokens.slice(i, i + 500);
      const res = await admin.messaging().sendEachForMulticast({
        tokens: batch,
        notification: { title, body },
        data: { broadcastId, communityId, type: "broadcast" },
      });
      logger.info("fcm sent", { broadcastId, success: res.successCount, failure: res.failureCount });
      // TODO(prod): prune tokens where res.responses[i].error is
      // messaging/registration-token-not-registered from the subscription doc.
    }
  }
);

// ─────────────────────────────────────────────────────────────────────────────
// B5.4  onSubscriptionChange — keep FCM community topic membership in sync.
// ─────────────────────────────────────────────────────────────────────────────
exports.onSubscriptionChange = onDocumentWritten("subscriptions/{subId}", async (event) => {
  const before = event.data.before.exists ? event.data.before.data() : null;
  const after = event.data.after.exists ? event.data.after.data() : null;
  const topic = (cid) => `community_${cid}`;
  const messaging = admin.messaging();

  // Became active (or created) with tokens → subscribe.
  if (after && after.active === true && (after.deviceTokens || []).length) {
    await messaging.subscribeToTopic(after.deviceTokens, topic(after.communityId));
    logger.info("topic subscribed", { subId: event.params.subId, communityId: after.communityId });
  }

  // Deleted or turned off → unsubscribe the previously-known tokens.
  if ((!after || after.active === false) && before && (before.deviceTokens || []).length) {
    await messaging.unsubscribeFromTopic(before.deviceTokens, topic(before.communityId));
    logger.info("topic unsubscribed", { subId: event.params.subId, communityId: before.communityId });
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// grantAdmin — an existing admin writes /adminGrants/{id}; this sets the claim.
// Firestore-triggered (no public endpoint → avoids the org's public-invoker block).
// ─────────────────────────────────────────────────────────────────────────────
exports.grantAdmin = onDocumentCreated("adminGrants/{id}", async (event) => {
  const snap = event.data;
  if (!snap) return;
  const email = (snap.data().email || "").trim();
  const revoke = snap.data().revoke === true;
  try {
    const user = await admin.auth().getUserByEmail(email);
    const claims = user.customClaims || {};
    await admin.auth().setCustomUserClaims(user.uid, { ...claims, admin: !revoke });
    await snap.ref.update({
      status: revoke ? "revoked" : "granted",
      uid: user.uid,
      processedAt: admin.firestore.FieldValue.serverTimestamp(),
    });
    logger.info("admin claim updated", { email, admin: !revoke });
  } catch (e) {
    await snap.ref.update({
      status: "error",
      error: e.message,
      processedAt: admin.firestore.FieldValue.serverTimestamp(),
    });
    logger.error("admin grant failed", { email, error: e.message });
  }
});

// ─────────────────────────────────────────────────────────────────────────────
// Room lifecycle (in-hospital iPads; room number IS the identity, one patient
// stay long). Jamf/HL7 wipes the DEVICE only, so the backend erases via:
//   1. purge-on-rebind (registerRoom wipes the previous binding)  ← hard guarantee
//   2. roomJanitor (heartbeat timeout)
//   3. admin "Erase room" → /roomCleanups doc  (manual, immediate)
// ─────────────────────────────────────────────────────────────────────────────

/** Erase everything bound to a room: auth user, subscriptions, inbox, binding. */
async function purgeRoom(roomNo) {
  const bindRef = db.doc(`rooms/${roomNo}`);
  const bind = await bindRef.get();
  if (!bind.exists) return { purged: false };
  const uid = bind.get("uid");
  if (uid) {
    const subs = await db.collection("subscriptions").where("uid", "==", uid).get();
    const writer = db.bulkWriter();
    subs.forEach((d) => writer.delete(d.ref));
    const inbox = await db.collection(`users/${uid}/inbox`).get();
    inbox.forEach((d) => writer.delete(d.ref));
    writer.delete(db.doc(`users/${uid}`));
    await writer.close();
    await admin.auth().deleteUser(uid).catch(() => {}); // may already be gone
  }
  await bindRef.delete();
  logger.info("room purged", { roomNo, uid });
  return { purged: true, uid };
}

// registerRoom — device (anonymous auth) writes /roomRegistrations {appToken, roomNo}.
// Validates the shared app token + room registry, purges any previous binding,
// then binds this uid to the room. Device polls its registration doc for status.
exports.registerRoom = onDocumentCreated("roomRegistrations/{id}", async (event) => {
  const snap = event.data;
  if (!snap) return;
  const { appToken, roomNo, uid } = snap.data();
  const fail = (reason) =>
    snap.ref.update({ status: "rejected", reason,
      processedAt: admin.firestore.FieldValue.serverTimestamp() });

  const cfg = await db.doc("config/registration").get();
  if (!cfg.exists || !appToken || appToken !== cfg.get("secret")) {
    logger.warn("registerRoom bad token", { roomNo });
    return fail("invalid app token");
  }
  const reg = await db.doc(`roomRegistry/${roomNo}`).get();
  if (!reg.exists || reg.get("active") !== true) return fail(`unknown or inactive room '${roomNo}'`);

  // Idempotency guard: same uid re-registering its own room must NOT purge itself.
  const existing = await db.doc(`rooms/${roomNo}`).get();
  if (existing.exists && existing.get("uid") === uid) {
    await existing.ref.update({ heartbeatAt: admin.firestore.FieldValue.serverTimestamp() });
    await snap.ref.update({ status: "registered", note: "already registered",
      processedAt: admin.firestore.FieldValue.serverTimestamp() });
    return;
  }

  await purgeRoom(roomNo); // previous patient stay (different uid) — hard erase
  await db.doc(`rooms/${roomNo}`).set({
    uid,
    registeredAt: admin.firestore.FieldValue.serverTimestamp(),
    heartbeatAt: admin.firestore.FieldValue.serverTimestamp(),
  });
  await snap.ref.update({ status: "registered",
    processedAt: admin.firestore.FieldValue.serverTimestamp() });
  logger.info("room registered", { roomNo, uid });
});

// cleanupRoom — admin (console button) or future ADT bridge writes /roomCleanups.
exports.cleanupRoom = onDocumentCreated("roomCleanups/{id}", async (event) => {
  const snap = event.data;
  if (!snap) return;
  const roomNo = snap.data().roomNo;
  const res = await purgeRoom(roomNo);
  await snap.ref.update({ status: res.purged ? "purged" : "no-binding",
    processedAt: admin.firestore.FieldValue.serverTimestamp() });
});

// roomJanitor — daily: purge rooms whose device stopped heartbeating (wiped by
// Jamf and never re-registered). 72h grace.
exports.roomJanitor = onSchedule({ schedule: "every day 04:00", timeZone: "America/Denver" }, async () => {
  const cutoff = admin.firestore.Timestamp.fromMillis(Date.now() - 72 * 3600 * 1000);
  const stale = await db.collection("rooms").where("heartbeatAt", "<", cutoff).get();
  for (const d of stale.docs) await purgeRoom(d.id);
  logger.info("roomJanitor done", { purged: stale.size });
});

// ─────────────────────────────────────────────────────────────────────────────
// B5.5  trimInboxes — nightly, cap each user's inbox at INBOX_CAP most recent.
// ─────────────────────────────────────────────────────────────────────────────
exports.trimInboxes = onSchedule({ schedule: "every day 03:00", timeZone: "America/Denver" }, async () => {
  const users = await db.collection("users").get(); // POC scale: iterate all users
  let trimmed = 0;
  for (const userDoc of users.docs) {
    const overflow = await userDoc.ref
      .collection("inbox")
      .orderBy("sentAt", "desc")
      .offset(INBOX_CAP)
      .get();
    if (overflow.empty) continue;
    const writer = db.bulkWriter();
    overflow.forEach((d) => writer.delete(d.ref));
    await writer.close();
    trimmed += overflow.size;
  }
  logger.info("trimInboxes complete", { trimmed });
});
