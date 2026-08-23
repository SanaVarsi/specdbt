from specdbt.typing_utils import coerce_scalar


def test_coerces_integers():
    assert coerce_scalar("42") == 42
    assert isinstance(coerce_scalar("42"), int)


def test_coerces_floats():
    assert coerce_scalar("18.2") == 18.2
    assert isinstance(coerce_scalar("18.2"), float)


def test_coerces_booleans():
    assert coerce_scalar("true") is True
    assert coerce_scalar("True") is True
    assert coerce_scalar("false") is False
    assert coerce_scalar("False") is False


def test_leaves_plain_strings_as_strings():
    assert coerce_scalar("brightsky") == "brightsky"


def test_leaves_empty_string_as_empty_string():
    assert coerce_scalar("") == ""


def test_coerces_explicit_null_literal_to_none():
    assert coerce_scalar("NULL") is None


def test_preserves_leading_zeros_as_strings():
    # "007" is an identifier-shaped value, not the integer 7 -- real numbers
    # aren't written with leading zeros, so this must not silently corrupt IDs.
    assert coerce_scalar("007") == "007"


def test_does_not_coerce_scientific_notation():
    # avoid the "1e5" -> 100000.0 surprise for values that were never meant
    # to be read as numbers at all.
    assert coerce_scalar("1e5") == "1e5"


def test_coerces_negative_numbers():
    assert coerce_scalar("-5") == -5
    assert coerce_scalar("-0.5") == -0.5
