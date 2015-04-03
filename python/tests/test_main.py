# local
from bugs.main import (
    walk_tree,
    dict_to_str
)


def test_dict_to_str():
    assert ["a: 1", "b: 2"] == sorted(dict_to_str(dict(
        a=1,
        b=2
    ), pairs_separator=";").split(";"))


def test_walk_emtpy_tree():
    assert [] == list(walk_tree({}))


def test_walk_tree():
    # given
    dict_2_levels = dict(
        a=dict(
            ka="va",
            ka2="va2",
        ),
        b=dict(
            kb="vb",
            kb2="vb2",
        )
    )

    # excercise
    actual = walk_tree(dict_2_levels)
    # verify
    assert [
        ('a', 'ka', 'va'),
        ('a', 'ka2', 'va2'),
        ('b', 'kb', 'vb'),
        ('b', 'kb2', 'vb2'),
    ] == list(sorted(actual))
