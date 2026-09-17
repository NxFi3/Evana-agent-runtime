"""Unit tests for the :mod:`calculator` module.

The tests exercise the four arithmetic functions defined in
``calculator.py``.  They cover normal operation as well as the
division-by-zero edge case.
"""

import pytest

from calculator import add, subtract, multiply, divide


def test_add():
    assert add(1, 2) == 3
    assert add(-1, 1) == 0
    assert add(1.5, 2.5) == 4.0


def test_subtract():
    assert subtract(5, 3) == 2
    assert subtract(0, 5) == -5
    assert subtract(2.5, 1.5) == 1.0


def test_multiply():
    assert multiply(3, 4) == 12
    assert multiply(-2, 3) == -6
    assert multiply(2.0, 3.5) == 7.0


def test_divide():
    assert divide(10, 2) == 5
    assert divide(9, 3) == 3
    assert divide(7, 2) == 3.5
    with pytest.raises(ZeroDivisionError):
        divide(1, 0)

