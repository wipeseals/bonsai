import pytest
from bonsai.util import byte_width


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
    assert byte_width(src_width) == expected_width
