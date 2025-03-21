SCRIPT = """
import sys
import json
import inspect
import ast

# Embedded user code begins here
{user_code}
# Embedded user code ends here

{input_data}
{expected}

def is_floats(x) -> bool:
    # check if it is float; List[float]; Tuple[float]
    if isinstance(x, float):
        return True
    if isinstance(x, (list, tuple)):
        return all(isinstance(i, float) for i in x)
    return False


def assertion(out, exp, atol=0):
    exact_match = str(out) == str(exp) or out == exp

    if atol == 0 and is_floats(exp):
        atol = 1e-6
    if not exact_match and atol != 0:
        assert all(abs(a - b) <= atol for a, b in zip(out, exp))
    else:
        assert exact_match

def main():
    # Get all names defined in the global scope
    global_names = globals()

    # Find the Solution class
    Solution = None
    function_name = None
    for name, obj in global_names.items():
        if name == "Solution" and inspect.isclass(obj):
            Solution = obj
            break

    # Find the entry point method within Solution class
    if Solution:
        for name, method in inspect.getmembers(Solution, inspect.isfunction):
            # Skip dunder methods
            if name.startswith('__') and name.endswith('__'):
                continue
            # The first non-dunder method is likely the solution
            function_name = name
            break

    # Create an instance and call the method
    try:
        result = None
        if Solution and function_name:
            instance = Solution()
            method = getattr(instance, function_name)
            if isinstance(input_data, list):
                # Handle different input formats
                if len(input_data) == 1 and isinstance(input_data[0], list):
                    # Single array argument
                    result = method(input_data[0])
                else:
                    # Multiple arguments
                    result = method(*input_data)
            else:
                # Single non-array argument
                result = method(input_data)

            # Check if result matches expected output
            print(result)
            assertion(result, expected)
            exit(0)
        else:
            print("No solution class or function found", file=sys.stderr)
            exit(2)
    except AssertionError as e:
        print("AssertionError: ", str(e), file=sys.stderr)
        exit(1)
    except Exception as e:
        # Any exception during execution counts as failure
        print("Exception: ", str(e), file=sys.stderr)
        exit(3)

if __name__ == "__main__":
    main()
"""
