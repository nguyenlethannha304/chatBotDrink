from app.services.onboarding import parse_caffeine, parse_list, parse_temperature


def test_parse_list_commas_and_and():
    assert parse_list("sweet, creamy and a bit sour") == ["sweet", "creamy", "a bit sour"]


def test_parse_list_strips_filler():
    assert parse_list("I like coffee and tea") == ["coffee", "tea"]


def test_parse_list_none_answers():
    assert parse_list("none") == []
    assert parse_list("No, nothing really") == []
    assert parse_list("n/a") == []


def test_parse_temperature():
    assert parse_temperature("I love hot drinks") == "hot"
    assert parse_temperature("iced please") == "iced"
    assert parse_temperature("cold ones") == "iced"
    assert parse_temperature("either is fine") == "either"
    assert parse_temperature("hot or iced, both work") == "either"
    assert parse_temperature("whatever") == "either"


def test_parse_caffeine():
    assert parse_caffeine("no caffeine for me") == "none"
    assert parse_caffeine("decaf only") == "none"
    assert parse_caffeine("just a little") == "low"
    assert parse_caffeine("any amount is fine") == "any"
