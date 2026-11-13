"""Generate the key pair for health educator single sign-on.

Prints two one-line values (base64-encoded PEM, safe to paste into a .env):

    HEALTH_EDUCATOR_SSO_PRIVATE_KEY   -> this server's .env ONLY
    SSO_PUBLIC_KEY                    -> the health educator portal's .env

Run it on the smart home server and never commit or share the private line.
Re-running makes a NEW pair; both sides must then be updated together.

    python scripts/gen_health_educator_sso_key.py
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def main() -> None:
    key = ec.generate_private_key(ec.SECP256R1())
    private = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    public = key.public_key().public_bytes(
        serialization.Encoding.PEM,
        serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    print("# smart home server .env (keep secret):")
    print(f"HEALTH_EDUCATOR_SSO_PRIVATE_KEY={base64.b64encode(private).decode()}")
    print()
    print("# health educator portal .env (public key, not secret):")
    print(f"SSO_PUBLIC_KEY={base64.b64encode(public).decode()}")


if __name__ == "__main__":
    main()
