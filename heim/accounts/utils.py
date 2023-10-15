import base64
import hashlib
import hmac
import math
import secrets


def hash_password(password: str, /, iterations: int = 400000) -> str:
    """
    Hash the provided password with a randomly-generated salt and return the
    salt and hash to store in the database.
    """

    algorithm = "sha256"
    salt = get_salt()
    password_hash = hashlib.pbkdf2_hmac(
        algorithm, password.encode(), salt.encode(), iterations
    )
    encoded_password = base64.b64encode(password_hash).decode("ascii").strip()

    return f"{algorithm}|{salt}|{iterations}|{encoded_password}"


def compare_password(*, stored_password: str, provided_password: str) -> bool:
    """
    Given a previously-stored salt and hash, and a password provided by a user
    trying to log in, check whether the password is correct. This assumes that
    the password_hash is well-formed.
    """

    algorithm, salt, iterations, encoded_password = stored_password.split("|", 4)
    password_hash = base64.b64decode(encoded_password)

    return hmac.compare_digest(
        password_hash,
        hashlib.pbkdf2_hmac(
            algorithm, provided_password.encode(), salt.encode(), int(iterations)
        ),
    )


RANDOM_STRING_CHARS = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def get_salt(entropy: int = 128) -> str:
    """
    Generate a cryptographically secure nonce salt in ASCII with an entropy
    of at least `entropy` bits.
    """

    char_count = math.ceil(entropy / math.log2(len(RANDOM_STRING_CHARS)))
    return get_random_string(char_count)


def get_random_string(length: int, allowed_chars: str = RANDOM_STRING_CHARS) -> str:
    """
    Return a securely generated random string.

    The bit length of the returned value can be calculated with the formula:
        log_2(len(allowed_chars)^length)

    For example, with default `allowed_chars` (26+26+10), this gives:
      * length: 12, bit length =~ 71 bits
      * length: 22, bit length =~ 131 bits

    NOTE: This method is copied from Django
    """

    return "".join(secrets.choice(allowed_chars) for i in range(length))
