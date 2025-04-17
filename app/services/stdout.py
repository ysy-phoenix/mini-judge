from typing import Any

import numpy as np


def stripped_string_compare(s1: str, s2: str) -> bool:
    s1 = s1.lstrip().rstrip()
    s2 = s2.lstrip().rstrip()
    is_equal = s1 == s2
    if is_equal:
        return True

    # Edge case: Check if s1 and s2 are floats.
    try:
        s1_float = float(s1)
        s2_float = float(s2)
        is_equal = np.isclose(s1_float, s2_float)
        return is_equal
    except Exception:
        pass

    # Edge case: Check if s1 and s2 rows are equal.
    s1_list = s1.split("\n")
    s2_list = s2.split("\n")
    s1_list = [s.lstrip().rstrip() for s in s1_list]
    s2_list = [s.lstrip().rstrip() for s in s2_list]

    s1_list = [s for s in s1_list if s]
    s2_list = [s for s in s2_list if s]
    if len(s1_list) != len(s2_list):
        return False

    for s1, s2 in zip(s1_list, s2_list, strict=False):
        sub_s1_list = s1.split()
        sub_s2_list = s2.split()
        sub_s1_list = [s.lstrip().rstrip() for s in sub_s1_list]
        sub_s2_list = [s.lstrip().rstrip() for s in sub_s2_list]
        sub_s1_list = [s for s in sub_s1_list if s]
        sub_s2_list = [s for s in sub_s2_list if s]
        if len(sub_s1_list) != len(sub_s2_list):
            return False
        for sub_s1, sub_s2 in zip(sub_s1_list, sub_s2_list, strict=False):
            if sub_s1 != sub_s2:
                # If they are floats...
                try:
                    sub_s1_float = float(sub_s1)
                    sub_s2_float = float(sub_s2)
                    if not np.isclose(sub_s1_float, sub_s2_float):
                        return False
                except Exception:
                    pass
    return True


def check_equal(stdout: Any, expected: Any, debug: bool = False) -> bool:
    if stripped_string_compare(str(stdout), str(expected)):
        return True

    if isinstance(stdout, list):
        output_1 = "\n".join(stdout)
        if stripped_string_compare(output_1, expected):
            return True

    if isinstance(stdout, list):
        output_2 = [o.lstrip().rstrip() for o in stdout]
        output_2 = "\n".join(output_2)
        if stripped_string_compare(output_2, expected):
            return True

    tmp_result = False
    # ground truth sequences are expressed as lists not tuples
    if isinstance(expected, tuple):
        expected = list(expected)

    try:
        tmp_result = stdout == [expected]
        if isinstance(expected, list):
            tmp_result = tmp_result or (stdout == expected)
            if isinstance(stdout[0], str):
                tmp_result = tmp_result or ([e.strip() for e in stdout] == expected)
    except Exception as e:
        if debug:
            print(f"Failed check1 exception = {e}")
        pass
    if tmp_result:
        return True

    # try one more time without \n
    if isinstance(expected, list):
        for tmp_index, i in enumerate(expected):
            expected[tmp_index] = i.split("\n")
            expected[tmp_index] = [x.strip() for x in expected[tmp_index] if x]
    else:
        expected = expected.split("\n")
        expected = list(filter(len, expected))
        expected = [x.strip() for x in expected]

    try:
        tmp_result = stdout == [expected]
        if isinstance(expected, list):
            tmp_result = tmp_result or (stdout == expected)
    except Exception as e:
        if debug:
            print(f"Failed check2 exception = {e}")
        pass
    if tmp_result:
        return True

    # try by converting the output into a split up list too
    if isinstance(stdout, list):
        stdout = list(filter(len, stdout))
    try:
        tmp_result = stdout == [expected]
        if isinstance(expected, list):
            tmp_result = tmp_result or (stdout == expected)
    except Exception as e:
        if debug:
            print(f"Failed check3 exception = {e}")
        pass
    if tmp_result:
        return True

    try:
        output_float = [float(e) for e in stdout]
        gt_float = [float(e) for e in expected]
        tmp_result = tmp_result or (
            (len(output_float) == len(gt_float)) and np.allclose(output_float, gt_float)
        )
    except Exception:
        pass
    try:
        if isinstance(stdout[0], list):
            output_float = [float(e) for e in stdout[0]]
            gt_float = [float(e) for e in expected[0]]
            tmp_result = tmp_result or (
                (len(output_float) == len(gt_float)) and np.allclose(output_float, gt_float)
            )
    except Exception:
        pass
    if tmp_result:
        return True

    if isinstance(expected, list):
        for tmp_index, i in enumerate(expected):
            expected[tmp_index] = set(i.split())
    else:
        expected = set(expected.split())

    try:
        tmp_result = stdout == expected
    except Exception as e:
        if debug:
            print(f"Failed check4 exception = {e}")
    if tmp_result:
        return True

    # try by converting the output into a split up list too
    if isinstance(stdout, list):
        for tmp_index, i in enumerate(stdout):
            stdout[tmp_index] = i.split()
        stdout = list(filter(len, stdout))
        for tmp_index, i in enumerate(stdout):
            stdout[tmp_index] = set(i)
    else:
        stdout = stdout.split()
        stdout = list(filter(len, stdout))
        stdout = set(stdout)
    try:
        tmp_result = {frozenset(s) for s in stdout} == {frozenset(s) for s in expected}
    except Exception as e:
        if debug:
            print(f"Failed check5 exception = {e}")

    # if they are all numbers, round so that similar numbers are treated as identical
    try:
        tmp_result = tmp_result or (
            {frozenset(round(float(t), 3) for t in s) for s in stdout}
            == {frozenset(round(float(t), 3) for t in s) for s in expected}
        )
    except Exception as e:
        if debug:
            print(f"Failed check6 exception = {e}")

    if tmp_result:
        return True

    return False
