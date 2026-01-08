# Changes for Testing Without Home Assistant

## Summary

Added **TEST_MODE** feature to allow testing the complete voice authentication flow without requiring Home Assistant to be running.

## Modified Files

### 1. config.py
**Added:**
```python
# Test mode (set to True to test without Home Assistant)
TEST_MODE = True  # Set to False when you have Home Assistant running
```

### 2. home_assistant.py
**Modified:** `trigger_scene()` function
- Now checks `TEST_MODE` flag
- When `TEST_MODE = True`: Prints formatted console output instead of calling Home Assistant
- When `TEST_MODE = False`: Makes actual HTTP request to Home Assistant

**Console output format:**
```
============================================================
🏠 HOME ASSISTANT SCENE TRIGGER
============================================================
Timestamp:    2026-01-06 18:27:19
Scene:        Night Scene
Scene ID:     night_scene
Source:       Alexa Voice Authentication
Status:       ✓ SUCCESS
============================================================
```

**Modified:** `test_connection()` function
- When `TEST_MODE = True`: Returns success message without testing connection
- When `TEST_MODE = False`: Actually tests Home Assistant connection

### 3. test_automation.py (NEW FILE)
Complete test simulation script that demonstrates:
- Full authentication flow
- Failed authentication handling
- Spoken variation testing
- Console output examples

## How to Use

### Testing Mode (Current Setup)
1. TEST_MODE is **enabled by default**
2. Run simulation: `python test_automation.py`
3. Start server: `python server.py` (or `./start.sh`)
4. Scene triggers will print to console

### Production Mode (When you have Home Assistant)
1. Edit `config.py`:
   ```python
   TEST_MODE = False
   HA_URL = "http://YOUR_HOME_ASSISTANT_IP:8123"
   ```
2. Set up Home Assistant webhook automation
3. Start server: `python server.py`
4. Scene triggers will call Home Assistant

## Benefits

✅ Test the complete flow without Home Assistant
✅ Verify challenge generation and validation
✅ See exactly what would be sent to Home Assistant
✅ Debug Alexa integration independently
✅ Easy toggle between test and production modes

## Updated Documentation

- README.md: Added "Testing Without Home Assistant" section
- SETUP.md: Added test_automation.py instructions
- All original functionality preserved when TEST_MODE = False
