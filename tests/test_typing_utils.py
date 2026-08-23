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
