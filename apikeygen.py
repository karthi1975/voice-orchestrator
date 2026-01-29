
import secrets
import base64

api_key = base64.b64encode(secrets.token_bytes(32)).decode()
ota_pass = secrets.token_hex(8)

print(f'api_encryption_key: \"{api_key}\"')
print(f'ota_password: \"{ota_pass}\"')