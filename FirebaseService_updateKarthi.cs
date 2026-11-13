using Smartroom.Models;
using Smartroom.ViewModels;
using Plugin.Firebase.CloudMessaging;
using Plugin.Firebase.Auth;
using Plugin.Firebase.Firestore;
using System;
using System.Collections.Generic;
using System.Text;
using System.Runtime.InteropServices;

namespace Smartroom.Services
{
    public class FirebaseService(ControlViewModel context)
    {
        // ADDED: heartbeat timer — keep as a field so it isn't garbage-collected
        private System.Threading.Timer heartbeatTimer;

        public async void SignIn()
        {
            // ADDED: self-healing re-entry — stop any old heartbeat before re-pairing
            heartbeatTimer?.Dispose();

            await CrossFirebaseCloudMessaging.Current.CheckIfValidAsync();
            var token = "cc106177cadba3d98e4a59f67090e97da166fe4433d6634b";

            var result = await CrossFirebaseAuth.Current.SignInAnonymouslyAsync();
            //           var uid = result.Uid ?? "";
            var db = CrossFirebaseFirestore.Current;

            var num = "R" + RoomState.GetRoomNumber();

            var uid = CrossFirebaseAuth.Current.CurrentUser.Uid;
            // instead of result.Uid ?? ""

            var regiDoc = db.GetCollection("roomRegistrations").CreateDocument();

            await regiDoc.SetDataAsync(new Dictionary<object, object>
                {
                    {  "uid", uid },
                    {  "appToken", token },
                    { "roomNo", num },
                    { "status", "pending" }
                },SetOptions.Merge());

            var listener = regiDoc.AddSnapshotListener<HAListener>(snapshot =>
                 {
                     HAListener data = snapshot.Data;

                     if (data.status == "registered")
                     {
                         CreateSubscription(db,uid,num);
                         StartHeartbeat(db, num);   // ADDED: begin twice-daily heartbeat once paired
                     }
                     else if (data.status.Contains("rejected"))
                     {
                         Console.WriteLine("Firebase has rejected the attempt to register. Reason: "+ data.status);
                     }

                 });
        }

        private async void CreateSubscription(IFirebaseFirestore db,string uid,string num)
        {
          var doc =  db.GetDocument($"subscriptions/{uid}_smartroom");
           await doc.SetDataAsync(new Dictionary<object,object>
            {
                { "uid", uid}, 
                { "communityId", "smartroom"},
                { "active", true },
                { "rooms", new string[]{num} },
                {"deviceTokens", new string[]{await CrossFirebaseCloudMessaging.Current.GetTokenAsync()} }
            });
                
        }


        private void FetchMessages()
        {

        }

        // ADDED: heartbeat + self-healing.
        // Fires immediately, then every 12h (server purges after 72h of silence).
        // Rules allow updating ONLY heartbeatAt — any other field gets the write denied.
        // If the write throws, the room was purged (rebind/janitor/admin erase):
        // dispose the timer and re-run SignIn() to re-pair from scratch.
        private void StartHeartbeat(IFirebaseFirestore db, string num)
        {
            heartbeatTimer = new System.Threading.Timer(async _ =>
            {
                try
                {
                    await db.GetDocument($"rooms/{num}")
                        .UpdateDataAsync(("heartbeatAt", FieldValue.ServerTimestamp()));
                }
                catch
                {
                    heartbeatTimer?.Dispose();
                    SignIn();   // purged → start over from step 1
                }
            }, null, TimeSpan.Zero, TimeSpan.FromHours(12));
        }

    }

    public class HAListener
    {
        [FirestoreProperty("uid")]
        public string uid { get; set; }

        [FirestoreProperty("appToken")]
        public string appToken { get; set; }

        [FirestoreProperty("roomNo")]
        public string roomNo{ get; set; }

        [FirestoreProperty("status")]
        public string status { get; set; }

        public HAListener(string id, string t, string rno, string s)
        {
            uid = id;
            appToken = t;
            roomNo  = rno;
            status = s;
        }

        public HAListener() { }
    }


}