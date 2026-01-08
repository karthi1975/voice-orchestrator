"""
Integration tests for Alexa and FutureProof Homes

Tests that both systems can coexist and work independently
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from server import app
from challenge import challenges


def setup_test_client():
    """Create Flask test client"""
    app.config['TESTING'] = True
    return app.test_client()


def clear_all_challenges():
    """Clear all challenges"""
    challenges['alexa'].clear()
    challenges['futureproofhome'].clear()


def test_storage_isolation():
    """Test that Alexa and FPH storage namespaces are isolated"""
    print("\n[TEST] Storage isolation between Alexa and FPH")
    clear_all_challenges()
    client = setup_test_client()

    # Create Alexa challenge (simulated via direct storage)
    from challenge import store_challenge
    store_challenge('alexa_session_123', 'ocean four', client_type='alexa')

    # Create FPH challenge via API
    fph_response = client.post(
        '/futureproofhome/auth/request',
        data=json.dumps({'home_id': 'home_1', 'intent': 'night_scene'}),
        content_type='application/json'
    )
    assert fph_response.status_code == 200

    # Verify both exist in separate namespaces
    assert 'alexa_session_123' in challenges['alexa']
    assert 'home_1' in challenges['futureproofhome']
    assert len(challenges['alexa']) == 1
    assert len(challenges['futureproofhome']) == 1

    print("✓ Alexa and FPH challenges stored in separate namespaces")
    print(f"✓ Alexa: {list(challenges['alexa'].keys())}")
    print(f"✓ FPH: {list(challenges['futureproofhome'].keys())}")


def test_concurrent_usage():
    """Test that Alexa and FPH can be used concurrently"""
    print("\n[TEST] Concurrent usage of Alexa and FPH")
    clear_all_challenges()
    client = setup_test_client()

    # Create multiple FPH challenges for different homes
    fph1 = client.post(
        '/futureproofhome/auth/request',
        data=json.dumps({'home_id': 'home_1', 'intent': 'night_scene'}),
        content_type='application/json'
    )
    challenge_fph1 = json.loads(fph1.data)['challenge']

    fph2 = client.post(
        '/futureproofhome/auth/request',
        data=json.dumps({'home_id': 'home_2', 'intent': 'lock_all'}),
        content_type='application/json'
    )
    challenge_fph2 = json.loads(fph2.data)['challenge']

    # Create Alexa challenges (simulated)
    from challenge import store_challenge
    store_challenge('alexa_session_1', 'apple one', client_type='alexa')
    store_challenge('alexa_session_2', 'banana two', client_type='alexa')

    # Verify all challenges exist
    assert len(challenges['alexa']) == 2
    assert len(challenges['futureproofhome']) == 2

    # Verify FPH challenge 1
    verify1 = client.post(
        '/futureproofhome/auth/verify',
        data=json.dumps({'home_id': 'home_1', 'response': challenge_fph1}),
        content_type='application/json'
    )
    data1 = json.loads(verify1.data)
    assert data1['status'] == 'approved'

    # Alexa challenges should still exist
    assert len(challenges['alexa']) == 2

    # Verify FPH challenge 2
    verify2 = client.post(
        '/futureproofhome/auth/verify',
        data=json.dumps({'home_id': 'home_2', 'response': challenge_fph2}),
        content_type='application/json'
    )
    data2 = json.loads(verify2.data)
    assert data2['status'] == 'approved'

    # Alexa challenges should STILL exist (not affected by FPH operations)
    assert len(challenges['alexa']) == 2

    print("✓ FPH operations don't affect Alexa challenges")
    print("✓ Multiple concurrent challenges handled correctly")


def test_shared_challenge_logic():
    """Test that both systems use the same challenge generation and validation"""
    print("\n[TEST] Shared challenge logic")
    clear_all_challenges()
    client = setup_test_client()

    # Generate FPH challenge
    fph_resp = client.post(
        '/futureproofhome/auth/request',
        data=json.dumps({'home_id': 'home_1', 'intent': 'night_scene'}),
        content_type='application/json'
    )
    fph_challenge = json.loads(fph_resp.data)['challenge']

    # Verify it follows expected format (word + number)
    parts = fph_challenge.split()
    assert len(parts) == 2
    assert parts[0].isalpha()
    assert parts[1].isalpha()  # Numbers are spelled out

    # Generate Alexa challenge (simulated)
    from challenge import generate_challenge
    alexa_challenge = generate_challenge()

    # Verify same format
    parts = alexa_challenge.split()
    assert len(parts) == 2
    assert parts[0].isalpha()
    assert parts[1].isalpha()

    print(f"✓ FPH challenge format: {fph_challenge}")
    print(f"✓ Alexa challenge format: {alexa_challenge}")
    print("✓ Both use same generation logic")


def test_independent_attempts_tracking():
    """Test that attempt counts are tracked independently"""
    print("\n[TEST] Independent attempts tracking")
    clear_all_challenges()
    client = setup_test_client()

    # Create FPH challenge
    fph_resp = client.post(
        '/futureproofhome/auth/request',
        data=json.dumps({'home_id': 'home_1', 'intent': 'night_scene'}),
        content_type='application/json'
    )

    # Make wrong attempts for FPH
    for i in range(2):
        client.post(
            '/futureproofhome/auth/verify',
            data=json.dumps({'home_id': 'home_1', 'response': 'wrong phrase'}),
            content_type='application/json'
        )

    # Verify FPH challenge still exists with 2 attempts
    assert 'home_1' in challenges['futureproofhome']
    assert challenges['futureproofhome']['home_1']['attempts'] == 2

    # Create Alexa challenge
    from challenge import store_challenge, validate_challenge
    store_challenge('alexa_session_1', 'apple one', client_type='alexa')

    # Verify Alexa challenge has 0 attempts (independent tracking)
    assert challenges['alexa']['alexa_session_1']['attempts'] == 0

    # Make a wrong attempt for Alexa
    validate_challenge('alexa_session_1', 'wrong', client_type='alexa')

    # Verify Alexa has 1 attempt, FPH still has 2
    assert challenges['alexa']['alexa_session_1']['attempts'] == 1
    assert challenges['futureproofhome']['home_1']['attempts'] == 2

    print("✓ Attempt counters are independent")
    print(f"✓ FPH attempts: 2, Alexa attempts: 1")


def run_all_tests():
    """Run all integration tests"""
    print("=" * 60)
    print("INTEGRATION TEST SUITE")
    print("=" * 60)

    tests = [
        test_storage_isolation,
        test_concurrent_usage,
        test_shared_challenge_logic,
        test_independent_attempts_tracking,
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
