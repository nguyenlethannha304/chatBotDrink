import pytest

from app.schemas import validate_phone


@pytest.mark.parametrize("raw,expected", [
    ("+14155550100", "+14155550100"),
    ("0912345678", "0912345678"),
    ("+84 91 234 5678", "+84912345678"),
    ("(415) 555-0100", "4155550100"),
])
def test_valid_phones(raw, expected):
    assert validate_phone(raw) == expected


@pytest.mark.parametrize("raw", [
    "12345",              # too short
    "1234567890123456",   # too long
    "phone123",           # letters
    "++123456789",        # double plus
    "",
])
def test_invalid_phones(raw):
    with pytest.raises(ValueError):
        validate_phone(raw)
