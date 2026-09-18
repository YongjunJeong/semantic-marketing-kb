from semantic_marketing_kb.taxonomy import AXES, Taxonomy


def test_loads_all_axes_and_resolves_aliases():
    t = Taxonomy()
    assert set(t.axes) == set(AXES)
    assert t.resolve("channel", "Push Alerts") == "ch:push"
    assert t.resolve("objective", "basket recovery") == "obj:recover_conversion"
    assert t.resolve("segment", "left items in cart") == "seg:cart_abandoner"
    assert t.resolve("channel", "ch:email") == "ch:email"


def test_unknown_labels_are_kept_not_dropped():
    t = Taxonomy()
    ids, unmapped = t.resolve_many("channel", ["email", "carrier pigeon", "email"])
    assert ids == ["ch:email"] and unmapped == ["carrier pigeon"]


def test_channel_groups():
    t = Taxonomy()
    assert t.group("ch:push") == "app" and t.group("ch:in_app") == "app" and t.group("ch:email") == "messaging"
