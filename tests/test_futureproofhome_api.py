"""
Test suite for FutureProof Homes API endpoints

Tests all four FPH API endpoints:
- POST /futureproofhome/auth/request
- POST /futureproofhome/auth/verify
- POST /futureproofhome/auth/cancel
- GET /futureproofhome/auth/status
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
from server import app
from challenge import challenges, clear_challenge


def setup_test_client():
    """Create Flask test client"""
    app.config['TESTING'] = True
    return app.test_client()


def clear_all_challenges():
    """Clear all challenges before each test"""
    challenges['alexa'].clear()
    challenges['futureproofhome'].clear()


def test_auth_request_success():
    """Test successful authentication request"""
    print("\n[TEST] Auth request - Success")
    clear_all_challenges()
    client = setup_test_client()

    # Make request
    response = client.post(
        '/futureproofhome/auth/request',
        data=json.dumps({'home_id': 'home_1', 'intent': 'night_scene'}),
        content_type='application/json'
    )

    # Verify response
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"

    data = json.loads(response.data)
    assert data['status'] == 'challenge'
    assert 'speech' in data
    assert 'challenge' in data
    assert len(data['challenge'].split()) == 2  # Should be "word number"

    # Verify challenge was stored
    assert 'home_1' in challenges['futureproofhome']
    assert challenges['futureproofhome']['home_1']['intent'] == 'night_scene'

    print(f"✓ Challenge generated: {data['challenge']}")
    print(f"✓ Speech: {data['speech']}")


def test_auth_request_missing_home_id():
    """Test auth request with missing home_id"""
    print("\n[TEST] Auth request - Missing home_id")
    clear_all_challenges()
    client = setup_test_client()

    response = client.post(
        '/futureproofhome/auth/request',
        data=json.dumps({'intent': 'night_scene'}),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data
    assert 'home_id' in data['error'].lower()

    print(f"✓ Correctly rejected: {data['error']}")


def test_auth_request_missing_intent():
    """Test auth request with missing intent"""
    print("\n[TEST] Auth request - Missing intent")
    clear_all_challenges()
    client = setup_test_client()

    response = client.post(
        '/futureproofhome/auth/request',
        data=json.dumps({'home_id': 'home_1'}),
        content_type='application/json'
    )

    assert response.status_code == 400
    data = json.loads(response.data)
    assert 'error' in data
    assert 'intent' in data['error'].lower()

    print(f"✓ Correctly rejected: {data['error']}")


def test_auth_verify_correct_response():
    """Test verification with correct response"""
    print("\n[TEST] Auth verify - Correct response")
    clear_all_challenges()
    client = setup_test_client()

    # First, request a challenge
    req_response = client.post(
        '/futureproofhome/auth/request',
        data=json.dumps({'home_id': 'home_1', 'intent': 'night_scene'}),
        content_type='application/json'
    )
    challenge = json.loads(req_response.data)['challenge']

    # Now verify with correct response
    verify_response = client.post(
        '/futureproofhome/auth/verify',
        data=json.dumps({'home_id': 'home_1', 'response': challenge}),
        content_type='application/json'
    )

    assert verify_response.status_code == 200
    data = json.loads(verify_response.data)
    assert data['status'] == 'approved'
    assert data['intent'] == 'night_scene'
    assert 'speech' in data

    # Verify challenge was cleared
    assert 'home_1' not in challenges['futureproofhome']

    print(f"✓ Verified challenge: {challenge}")
    print(f"✓ Intent returned: {data['intent']}")


def test_auth_verify_incorrect_response():
    """Test verification with incorrect response"""
    print("\n[TEST] Auth verify - Incorrect response")
    clear_all_challenges()
    client = setup_test_client()

    # Request a challenge
    req_response = client.post(
        '/futureproofhome/auth/request',
        data=json.dumps({'home_id': 'home_1', 'intent': 'night_scene'}),
        content_type='application/json'
    )
    challenge = json.loads(req_response.data)['challenge']

    # Verify with wrong response
    verify_response = client.post(
        '/futureproofhome/auth/verify',
        data=json.dumps({'home_id': 'home_1', 'response': 'wrong phrase'}),
        content_type='application/json'
    )

    assert verify_response.status_code == 200
    data = json.loads(verify_response.data)
    assert data['status'] == 'denied'
    assert data['reason'] == 'mismatch'
    assert 'attempts_remaining' in data

    # Challenge should still exist (not cleared)
    assert 'home_1' in challenges['futureproofhome']

    print(f"✓ Correctly denied wrong response")
    print(f"✓ Attempts remaining: {data['attempts_remaining']}")


def test_auth_verify_no_pending_challenge():
    """Test verification with no pending challenge"""
    print("\n[TEST] Auth verify - No pending challenge")
    clear_all_challenges()
    client = setup_test_client()

    response = client.post(
        '/futureproofhome/auth/verify',
        data=json.dumps({'home_id': 'home_1', 'response': 'ocean four'}),
        content_type='application/json'
    )

    assert response.status_code == 200
    data = json.loads(response.data)
    assert data['status'] == 'denied'
    assert data['reason'] == 'no_challenge'

    print(f"✓ Correctly denied - no challenge found")


def test_auth_cancel():
    """Test cancelling authentication"""
    print("\n[TEST] Auth cancel")
    clear_all_challenges()
    client = setup_test_client()

    # Create a challenge
    client.post(
        '/futureproofhome/auth/request',
        data=json.dumps({'home_id': 'home_1', 'intent': 'night_scene'}),
        content_type='application/json'
    )

    # Verify challenge exists
    assert 'home_1' in challenges['futureproofhome']

    # Cancel it
    cancel_response = client.post(
        '/futureproofhome/auth/cancel',
        data=json.dumps({'home_id': 'home_1'}),
        content_type='application/json'
    )

    assert cancel_response.status_code == 200
    data = json.loads(cancel_response.data)
    assert data['status'] == 'cancelled'

    # Verify challenge was cleared
    assert 'home_1' not in challenges['futureproofhome']

    print(f"✓ Challenge cancelled successfully")


def test_auth_status():
    """Test status endpoint"""
    print("\n[TEST] Auth status")
    clear_all_challenges()
    client = setup_test_client()

    # Create multiple challenges
    client.post(
        '/futureproofhome/auth/request',
        data=json.dumps({'home_id': 'home_1', 'intent': 'night_scene'}),
        content_type='application/json'
    )

    client.post(
        '/futureproofhome/auth/request',
        data=json.dumps({'home_id': 'home_2', 'intent': 'lock_all'}),
        content_type='application/json'
    )

    # Get status
    status_response = client.get('/futureproofhome/auth/status')

    assert status_response.status_code == 200
    data = json.loads(status_response.data)
    assert 'pending_challenges' in data
    assert 'config' in data
    assert 'total_pending' in data
    assert data['total_pending'] == 2

    # Verify challenge details
    assert 'home_1' in data['pending_challenges']
    assert 'home_2' in data['pending_challenges']
    assert data['pending_challenges']['home_1']['intent'] == 'night_scene'
    assert data['pending_challenges']['home_2']['intent'] == 'lock_all'

    print(f"✓ Status shows {data['total_pending']} pending challenges")
    print(f"✓ Config: expiry={data['config']['expiry_seconds']}s, max_attempts={data['config']['max_attempts']}")


def test_multiple_homes_isolation():
    """Test that challenges for different homes are isolated"""
    print("\n[TEST] Multiple homes isolation")
    clear_all_challenges()
    client = setup_test_client()

    # Create challenges for two different homes
    resp1 = client.post(
        '/futureproofhome/auth/request',
        data=json.dumps({'home_id': 'home_1', 'intent': 'night_scene'}),
        content_type='application/json'
    )
    challenge1 = json.loads(resp1.data)['challenge']

    resp2 = client.post(
        '/futureproofhome/auth/request',
        data=json.dumps({'home_id': 'home_2', 'intent': 'lock_all'}),
        content_type='application/json'
    )
    challenge2 = json.loads(resp2.data)['challenge']

    # Verify home_1's challenge with home_1
    verify1 = client.post(
        '/futureproofhome/auth/verify',
        data=json.dumps({'home_id': 'home_1', 'response': challenge1}),
        content_type='application/json'
    )
    data1 = json.loads(verify1.data)
    assert data1['status'] == 'approved'
    assert data1['intent'] == 'night_scene'

    # Verify home_2's challenge still exists
    assert 'home_2' in challenges['futureproofhome']

    # Verify home_2's challenge with home_2
    verify2 = client.post(
        '/futureproofhome/auth/verify',
        data=json.dumps({'home_id': 'home_2', 'response': challenge2}),
        content_type='application/json'
    )
    data2 = json.loads(verify2.data)
    assert data2['status'] == 'approved'
    assert data2['intent'] == 'lock_all'

    print(f"✓ Home isolation verified - challenges independent")


def test_normalization_variations():
    """Test that spoken variations are normalized correctly"""
    print("\n[TEST] Normalization variations")
    clear_all_challenges()
    client = setup_test_client()

    # Test variations - create a new challenge for each
    test_cases = [
        ("exact match", lambda c: c),
        ("uppercase", lambda c: c.upper()),
        ("extra whitespace", lambda c: f"  {c}  "),
        ("digit instead of word", lambda c: c.split()[0] + " " + {
            'zero': '0', 'one': '1', 'two': '2', 'three': '3', 'four': '4',
            'five': '5', 'six': '6', 'seven': '7', 'eight': '8', 'nine': '9'
        }.get(c.split()[1], c.split()[1]))
    ]

    for test_name, transform in test_cases:
        # Create a fresh challenge
        req_response = client.post(
            '/futureproofhome/auth/request',
            data=json.dumps({'home_id': 'home_1', 'intent': 'night_scene'}),
            content_type='application/json'
        )
        challenge = json.loads(req_response.data)['challenge']

        # Apply transformation
        variation = transform(challenge)

        # Verify
        verify_response = client.post(
            '/futureproofhome/auth/verify',
            data=json.dumps({'home_id': 'home_1', 'response': variation}),
            content_type='application/json'
        )
        data = json.loads(verify_response.data)
        assert data['status'] == 'approved', f"Failed for {test_name}: '{variation}' vs '{challenge}'"
        print(f"✓ {test_name} accepted: '{variation}'")


def run_all_tests():
    """Run all FutureProof Homes API tests"""
    print("=" * 60)
    print("FUTUREPROOFHOME API TEST SUITE")
    print("=" * 60)

    tests = [
        test_auth_request_success,
        test_auth_request_missing_home_id,
        test_auth_request_missing_intent,
        test_auth_verify_correct_response,
        test_auth_verify_incorrect_response,
        test_auth_verify_no_pending_challenge,
        test_auth_cancel,
        test_auth_status,
        test_multiple_homes_isolation,
        test_normalization_variations,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except AssertionError as e:
            failed += 1
            print(f"✗ FAILED: {e}")
        except Exception as e:
            failed += 1
            print(f"✗ ERROR: {e}")

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    exit(0 if success else 1)
