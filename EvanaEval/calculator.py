"""Simple calculator module.

This module provides four basic arithmetic functions:

* :func:`add` – returns the sum of two numbers.
* :func:`subtract` – returns the difference of two numbers.
* :func:`multiply` – returns the product of two numbers.
* :func:`divide` – returns the quotient of two numbers.

All functions accept numeric types (int or float) and return a numeric
result.  Division by zero raises a :class:`ZeroDivisionError` as per
Python's default behaviour.
"""

from __future__ import annotations

def add(a: float | int, b: float | int) -> float | int:
    """Return the sum of *a* and *b*.

    Parameters
    ----------
    a, b:
        Numbers to add.
    """
    return a + b


def subtract(a: float | int, b: float | int) -> float | int:
    """Return the difference of *a* and *b* (a - b)."""
    return a - b


def multiply(a: float | int, b: float | int) -> float | int:
    """Return the product of *a* and *b*."""
    return a * b


def divide(a: float | int, b: float | int) -> float:
    """Return the quotient of *a* divided by *b*.

    Raises
    ------
    ZeroDivisionError
        If *b* is zero.
    """
    return a / b

