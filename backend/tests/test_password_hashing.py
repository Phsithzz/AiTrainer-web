"""Password hashing must work with the installed bcrypt (5.x) and keep old hashes valid.

Regression: passlib 1.7.4's bcrypt backend runs a self-test with a >72-byte password,
which bcrypt 5 rejects with ValueError, so /auth/register and /auth/login returned 500.
"""
from auth import get_password_hash, verify_password

# A standard $2b$ bcrypt hash, the same format passlib stored in the users table.
EXISTING_HASH = "$2b$12$oeyzNOW6LDXhawdfjcEmp.gtwsJg8D7VcbBu.cNbrXr119aEAQLri"


def test_hash_then_verify_round_trip():
    hashed = get_password_hash("Secret123!")
    assert verify_password("Secret123!", hashed)


def test_wrong_password_is_rejected():
    hashed = get_password_hash("Secret123!")
    assert not verify_password("secret123!", hashed)


def test_existing_stored_hash_still_verifies():
    assert verify_password("legacy-pass-123", EXISTING_HASH)
    assert not verify_password("legacy-pass-124", EXISTING_HASH)


def test_password_longer_than_72_bytes_is_accepted():
    long_password = "ก" * 40  # 120 bytes in UTF-8
    hashed = get_password_hash(long_password)
    assert verify_password(long_password, hashed)


def test_malformed_hash_returns_false_instead_of_crashing():
    assert not verify_password("anything", "not-a-bcrypt-hash")
