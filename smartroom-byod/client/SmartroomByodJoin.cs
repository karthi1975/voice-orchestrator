// SmartroomByodJoin.cs — BYOD (relative's phone) join flow, for Aaron.
// Template: mirrors the iPad service's proven Plugin.Firebase patterns
// (CreateDocument() + SetDataAsync, [FirestoreProperty] listener classes).
// The phone NEVER registers, NEVER heartbeats, and NEVER holds the app token.
//
// QR on the wall iPad encodes:  SMARTROOM|R503|K7MP2X
// PIN path: user types the room number + the 6-char code shown on the iPad.
// Code charset is A-Z and 2-9 with no I/L/O/0/1 (safe to type).

public class JoinStatus
{
    [FirestoreProperty("status")] public string Status { get; set; }   // pending → joined | rejected
    [FirestoreProperty("reason")] public string Reason { get; set; }
}

public async Task JoinRoomAsync(string roomNo, string code)
{
    var auth = CrossFirebaseAuth.Current;
    if (auth.CurrentUser == null)
        await auth.SignInAnonymouslyAsync();
    var uid = auth.CurrentUser.Uid;
    var db = CrossFirebaseFirestore.Current;

    var joinDoc = db.GetCollection("roomJoins").CreateDocument();
    await joinDoc.SetDataAsync(new Dictionary<object, object>
    {
        ["uid"]    = uid,
        ["roomNo"] = roomNo.Trim(),
        ["code"]   = code.Trim().ToUpperInvariant(),
        ["status"] = "pending",
        // Optional, enables push + uninstall detection:
        // ["deviceTokens"] = new List<object> { await CrossFirebaseCloudMessaging.Current.GetTokenAsync() },
    }, SetOptions.Merge());

    joinDoc.AddSnapshotListener<JoinStatus>((snapshot, error) =>
    {
        var s = snapshot?.Data?.Status;
        if (s == "joined")   StartSession(db, uid);
        if (s == "rejected") ShowJoinError(snapshot.Data.Reason); // stale/rotated code → rescan the QR
    });
}

private void StartSession(IFirebaseFirestore db, string uid)
{
    // 1) Messages — the inbox model is identical to the iPad's
    //    (broadcastId, title, body, sentAt, read/readAt; mark-read + delete allowed).
    db.GetCollection($"users/{uid}/inbox")
      .OrderBy("sentAt", descending: true)
      .AddSnapshotListener<InboxMessage>((snapshot, error) => RenderMessages(snapshot));

    // 2) Session end — the server deleting my subscription IS the signal.
    //    Fires on discharge purge, rebind, 7-day expiry, or admin erase.
    db.GetDocument($"subscriptions/{uid}_smartroom")
      .AddSnapshotListener((snapshot, error) =>
      {
          if (snapshot != null && !snapshot.Exists)
              EndSession(); // clear local messages, show "This room's session has ended — scan the new QR to rejoin."
      });
}

// Re-joining any time with the room's CURRENT code renews the 7-day expiry
// (the join flow is idempotent per uid). After a purge the anonymous Auth user
// is deleted too: treat any auth/permission failure as "sign in anonymously
// again and rescan" — same self-heal rule as the iPad.
