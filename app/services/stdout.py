from functools import singledispatch
from typing import Any

import numpy as np


def is_numeric(value: str) -> bool:
    r"""Check if a string can be converted to a float."""
    try:
        float(value)
        return True
    except (ValueError, TypeError):
        return False


def floats_equal(v1: str | float, v2: str | float, rtol: float = 1e-5, atol: float = 1e-8) -> bool:
    r"""Compare two values as floats with tolerance."""
    try:
        return np.isclose(float(v1), float(v2), rtol=rtol, atol=atol)
    except (ValueError, TypeError):
        return False


def normalize_string(s: str) -> str:
    r"""Normalize a string by stripping whitespace and handling empty lines."""
    return "\n".join(line.strip() for line in s.split("\n") if line.strip())


def tokenize_string(s: str) -> list[list[str]]:
    r"""Split a string into a nested list of tokens (by line and then by word)."""
    return [line.split() for line in normalize_string(s).split("\n")]


def compare_tokenized(tokens1: list[list[str]], tokens2: list[list[str]]) -> bool:
    r"""Compare two tokenized string representations."""
    if len(tokens1) != len(tokens2):
        return False

    for line1, line2 in zip(tokens1, tokens2, strict=False):
        if len(line1) != len(line2):
            return False

        for t1, t2 in zip(line1, line2, strict=False):
            if t1 == t2:
                continue
            if is_numeric(t1) and is_numeric(t2) and floats_equal(t1, t2):
                continue
            return False

    return True


def compare_as_sets(tokens1: list[list[str]], tokens2: list[list[str]]) -> bool:
    r"""Compare tokenized strings as sets of words and as sets of numbers."""
    try:
        # Compare as sets of strings
        set1 = {frozenset(line) for line in tokens1}
        set2 = {frozenset(line) for line in tokens2}
        if set1 == set2:
            return True

        # Compare as sets of numbers (with rounding) if all elements are numeric
        if all(all(is_numeric(t) for t in line) for line in tokens1) and all(
            all(is_numeric(t) for t in line) for line in tokens2
        ):
            set1_numeric = {frozenset(round(float(t), 3) for t in line) for line in tokens1 if line}
            set2_numeric = {frozenset(round(float(t), 3) for t in line) for line in tokens2 if line}
            return set1_numeric == set2_numeric
    except Exception:
        pass

    return False


@singledispatch
def normalize_output(output: Any) -> str:
    r"""Convert any output to a normalized string representation."""
    return normalize_string(str(output))


@normalize_output.register
def _(output: list) -> str | list[list[str]]:
    r"""Handle list outputs specially, returning either a normalized string or tokenized list."""
    # Try as a single joined string
    joined = "\n".join(str(item) for item in output)

    # Also prepare a tokenized version for alternative comparison methods
    tokenized = []
    for item in output:
        if isinstance(item, str):
            tokenized.append(item.split())
        else:
            try:
                tokenized.append(str(item).split())
            except Exception:
                pass

    return joined, tokenized


def check_equal(stdout: Any, expected: Any, debug: bool = False) -> bool:
    r"""Comprehensively check if stdout matches the expected output.

    This function tries multiple approaches to determine equality:
    1. Direct string comparison after normalization
    2. Comparison as lists of lines
    3. Comparison as tokenized lines
    4. Comparison as sets
    5. Comparison as numeric values

    Args:
        stdout: The actual output (string, list, or other)
        expected: The expected output (string, list, or other)
        debug: If True, print debug information

    Returns:
        True if outputs match, False otherwise
    """
    try:
        # Convert tuples to lists for consistency
        if isinstance(expected, tuple):
            expected = list(expected)
        if isinstance(stdout, tuple):
            stdout = list(stdout)

        if isinstance(stdout, list) and isinstance(expected, list):
            if len(stdout) != len(expected):
                return False
            for s, e in zip(stdout, expected, strict=False):
                if not check_equal(s, e):
                    return False
            return True

        # Special case: direct equality
        if stdout == expected:
            return True

        # Normalize both outputs to strings
        stdout_norm = normalize_output(stdout)
        expected_norm = normalize_output(expected)

        # Handle the list case where we get both string and tokenized version
        stdout_tokenized = None
        if isinstance(stdout_norm, tuple):
            stdout_norm, stdout_tokenized = stdout_norm

        expected_tokenized = None
        if isinstance(expected_norm, tuple):
            expected_norm, expected_tokenized = expected_norm

        # Try direct string comparison after normalization
        if normalize_string(stdout_norm) == normalize_string(expected_norm):
            return True

        # Tokenize the strings for more complex comparisons
        if stdout_tokenized is None:
            stdout_tokenized = tokenize_string(stdout_norm)

        if expected_tokenized is None:
            expected_tokenized = tokenize_string(expected_norm)

        # Compare tokenized representations
        if compare_tokenized(stdout_tokenized, expected_tokenized):
            return True

        # Try comparing as sets
        if compare_as_sets(stdout_tokenized, expected_tokenized):
            return True

        # Try numeric comparison for lists of numbers
        try:
            if (
                isinstance(stdout, list)
                and isinstance(expected, list)
                and all(is_numeric(str(x)) for x in stdout)
                and all(is_numeric(str(x)) for x in expected)
            ):
                stdout_float = [float(x) for x in stdout]
                expected_float = [float(x) for x in expected]

                if len(stdout_float) == len(expected_float) and np.allclose(
                    stdout_float, expected_float
                ):
                    return True
        except Exception as e:
            if debug:
                print(f"Numeric comparison failed: {e}")

        return False

    except Exception as e:
        if debug:
            print(f"Equality check failed with error: {e}")
        return False
