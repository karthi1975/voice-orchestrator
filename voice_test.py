#!/usr/bin/env python3
"""
Voice testing for Alexa skill using local speech recognition
Captures voice → converts to text → sends to Alexa endpoint
"""

import speech_recognition as sr
import requests
import json
import uuid

ENDPOINT = "https://1eb143d2d314.ngrok-free.app/alexa"
SESSION_ID = f"voice-session-{uuid.uuid4()}"


def listen_for_speech():
    """Capture voice and convert to text"""
    recognizer = sr.Recognizer()

    with sr.Microphone() as source:
        print("\n🎤 Listening... (speak now)")
        print("💡 Adjusting for ambient noise... please wait")

        # Adjust for ambient noise
        recognizer.adjust_for_ambient_noise(source, duration=1)

        print("✅ Ready! Speak now...")
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            print("🔄 Processing speech...")

            # Use Google's speech recognition (free)
            text = recognizer.recognize_google(audio)
            print(f"✅ You said: '{text}'")
            return text.lower()

        except sr.WaitTimeoutError:
            print("❌ No speech detected (timeout)")
            return None
        except sr.UnknownValueError:
            print("❌ Could not understand audio")
            return None
        except sr.RequestError as e:
            print(f"❌ Speech recognition error: {e}")
            return None


def send_to_alexa(intent_name, text=None):
    """Send request to Alexa endpoint"""

    payload = {
        "version": "1.0",
        "session": {
            "sessionId": SESSION_ID,
            "application": {"applicationId": "amzn1.ask.skill.test"},
            "user": {"userId": "voice-test-user"}
        },
        "request": {
            "type": "IntentRequest",
            "requestId": f"req-{uuid.uuid4()}",
            "locale": "en-US",
            "intent": {
                "name": intent_name,
                "confirmationStatus": "NONE"
            }
        }
    }

    # Add response slot if provided
    if text and intent_name == "ChallengeResponseIntent":
        payload["request"]["intent"]["slots"] = {
            "response": {
                "name": "response",
                "value": text
            }
        }

    try:
        response = requests.post(ENDPOINT, json=payload, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"❌ Server error: {response.status_code}")
            return None
    except Exception as e:
        print(f"❌ Request failed: {e}")
        return None


def extract_alexa_speech(response):
    """Extract what Alexa says from response"""
    if not response:
        return None
    return response.get("response", {}).get("outputSpeech", {}).get("text", "")


def voice_test_flow():
    """Interactive voice test flow"""

    print("\n" + "="*60)
    print("🎤 VOICE-CONTROLLED ALEXA SKILL TESTER")
    print("="*60)
    print("\nThis will:")
    print("1. Capture your voice using your microphone")
    print("2. Convert speech to text (Google Speech Recognition)")
    print("3. Send to your Alexa skill endpoint")
    print("\nMake sure your microphone is connected!\n")

    input("Press Enter when ready to start...")

    # Step 1: Trigger night scene with voice
    print("\n" + "-"*60)
    print("STEP 1: Say 'night scene' or 'activate night scene'")
    print("-"*60)

    text = listen_for_speech()

    if not text:
        print("❌ Failed to capture speech. Try again.")
        return

    # Check if it matches night scene intent
    night_scene_phrases = ["night", "scene", "bedtime", "activate"]
    if any(phrase in text for phrase in night_scene_phrases):
        print("✅ Recognized as Night Scene intent!")

        response = send_to_alexa("NightSceneIntent")
        alexa_text = extract_alexa_speech(response)

        if alexa_text:
            print(f"\n🗣️  ALEXA: {alexa_text}")

            # Extract challenge
            if "Please say:" in alexa_text:
                challenge = alexa_text.split("Please say:")[-1].strip()
                print(f"\n💡 Challenge phrase: '{challenge}'")

                # Step 2: Listen for challenge response
                print("\n" + "-"*60)
                print(f"STEP 2: Say the challenge phrase: '{challenge}'")
                print("-"*60)

                response_text = listen_for_speech()

                if response_text:
                    # Send challenge response
                    response = send_to_alexa("ChallengeResponseIntent", response_text)
                    alexa_text = extract_alexa_speech(response)

                    if alexa_text:
                        print(f"\n🗣️  ALEXA: {alexa_text}")

                        if "verified" in alexa_text.lower():
                            print("\n🎉 SUCCESS! Voice authentication completed!")
                            print("📺 Check your server console for scene trigger")
                        else:
                            print("\n❌ Authentication failed")
    else:
        print(f"❌ '{text}' doesn't match night scene intent")
        print("Try saying: 'night scene' or 'activate night scene'")

    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60 + "\n")


def simple_voice_command():
    """Single voice command test"""

    print("\n🎤 Say your command (e.g., 'night scene')...")

    text = listen_for_speech()

    if text:
        # Map common phrases to intents
        if any(word in text for word in ["night", "scene", "bedtime"]):
            response = send_to_alexa("NightSceneIntent")
            alexa_text = extract_alexa_speech(response)
            print(f"\n🗣️  ALEXA: {alexa_text}\n")
        else:
            print(f"❌ Don't know how to handle: '{text}'")


def test_microphone():
    """Test if microphone is working"""

    print("\n🎤 Testing microphone...")
    print("Say anything to test...\n")

    text = listen_for_speech()

    if text:
        print(f"\n✅ Microphone is working! You said: '{text}'")
    else:
        print("\n❌ Microphone test failed")

    print()


def main():
    """Main menu"""

    print("\n" + "="*60)
    print("VOICE-CONTROLLED ALEXA SKILL TESTER")
    print("="*60)
    print("\n⚠️  REQUIREMENTS:")
    print("- Microphone connected")
    print("- Internet connection (for Google Speech API)")
    print("- Install: pip install SpeechRecognition pyaudio")

    while True:
        print("\n" + "-"*60)
        print("1. Full Voice Test (complete flow)")
        print("2. Simple Voice Command")
        print("3. Test Microphone")
        print("4. Exit")
        print("-"*60)

        choice = input("\nChoice (1-4): ").strip()

        if choice == "1":
            voice_test_flow()
        elif choice == "2":
            simple_voice_command()
        elif choice == "3":
            test_microphone()
        elif choice == "4":
            print("\n👋 Goodbye!\n")
            break
        else:
            print("Invalid choice")


if __name__ == "__main__":
    try:
        import speech_recognition
        main()
    except ImportError:
        print("\n❌ Missing required package!")
        print("\nInstall with:")
        print("  pip install SpeechRecognition pyaudio")
        print("\nOn macOS, you may also need:")
        print("  brew install portaudio")
        print("  pip install pyaudio\n")
