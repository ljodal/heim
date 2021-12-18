from weather_station.accounts.utils import compare_password, hash_password


def test_hash_password(password: str) -> None:
    expected_iterations = 1
    hashed_password = hash_password(password, iterations=expected_iterations)
    assert "|" in hashed_password
    algorithm, salt, actual_iterations, encoded_password = hashed_password.split("|")
    assert algorithm == "sha256"
    assert salt
    assert int(actual_iterations) == expected_iterations
    assert encoded_password != password


def test_password_hashing(password: str) -> None:
    hashed_password = hash_password(password)
    assert compare_password(stored_password=hashed_password, provided_password=password)
