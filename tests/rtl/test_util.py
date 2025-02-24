import pytest

from bonsai.rtl.calc import Calc


@pytest.mark.parametrize(
    "src_width, expected_width",
    [
        (1, 1),
        (7, 1),
        (8, 1),
        (9, 2),
        (16, 2),
        (32, 4),
        (64, 8),
        (65, 9),
    ],
)
def test_byte_width(src_width: int, expected_width: int):
    assert Calc.byte_width(src_width) == expected_width


@pytest.mark.parametrize(
    "src_width, expected",
    [
        (1, True),
        (2, True),
        (3, False),
        (4, True),
        (8, True),
        (16, True),
        (32, True),
        (64, True),
        (65, False),
    ],
)
def test_is_power_of_2(src_width: int, expected: bool):
    assert Calc.is_power_of_2(src_width) == expected
