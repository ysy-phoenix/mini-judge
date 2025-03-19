import ast

# Common types from the typing module
TYPING_TYPES: set[str] = {
    "List",
    "Dict",
    "Tuple",
    "Set",
    "FrozenSet",
    "Optional",
    "Union",
    "Any",
    "Generic",
    "TypeVar",
    "Callable",
    "Iterable",
    "Iterator",
    "Generator",
    "Sequence",
    "Mapping",
    "MutableMapping",
    "Type",
}

# Common classes and their modules - maps class name to module name
COMMON_CLASSES: dict[str, str] = {
    "collections": "collections",
    "deque": "collections",
    "defaultdict": "collections",
    "Counter": "collections",
    "OrderedDict": "collections",
    "namedtuple": "collections",
    "ChainMap": "collections",
    "Path": "pathlib",
    "re": "re",  # For 're' module itself
    "datetime": "datetime",
    "date": "datetime",
    "time": "datetime",
    "timedelta": "datetime",
    "BeautifulSoup": "bs4",
    "timeit": "timeit",
    "sleep": "time",
    "pickle": "pickle",
    "json": "json",
    "np": "numpy",
    "pd": "pandas",
    "plt": "matplotlib.pyplot",
    "heapq": "heapq",
    "bisect": "bisect",
    "lru_cache": "functools",
}

# Special cases - maps class name to complete import statement
DIRECT_IMPORTS: dict[str, str] = {
    "deque": "from collections import deque",
    "defaultdict": "from collections import defaultdict",
    "Counter": "from collections import Counter",
    "OrderedDict": "from collections import OrderedDict",
    "lru_cache": "from functools import lru_cache",
    "sleep": "from time import sleep",
}


class CodeAnalyzer(ast.NodeVisitor):
    r"""Analyze code to find used but not imported names."""

    def __init__(self):
        self.used_names = set()
        self.defined_names = set()
        self.imported_names = set()
        self.from_imports = {}

    def visit_Name(self, node):  # noqa: N802
        if isinstance(node.ctx, ast.Load):
            self.used_names.add(node.id)
        elif isinstance(node.ctx, ast.Store):
            self.defined_names.add(node.id)
        self.generic_visit(node)

    def visit_ClassDef(self, node):  # noqa: N802
        self.defined_names.add(node.name)
        self.generic_visit(node)

    def visit_FunctionDef(self, node):  # noqa: N802
        self.defined_names.add(node.name)
        self.generic_visit(node)

    def visit_Import(self, node):  # noqa: N802
        for name in node.names:
            self.imported_names.add(name.name.split(".")[0])
            if name.asname:
                self.defined_names.add(name.asname)
            else:
                self.defined_names.add(name.name.split(".")[0])

    def visit_ImportFrom(self, node):  # noqa: N802
        if node.module:
            self.imported_names.add(node.module.split(".")[0])
            if node.module not in self.from_imports:
                self.from_imports[node.module] = []
            for name in node.names:
                self.from_imports[node.module].append(name.name)
                if name.asname:
                    self.defined_names.add(name.asname)
                else:
                    self.defined_names.add(name.name)


def preprocess_user_code(code: str) -> str:
    r"""Add necessary imports to user code by analyzing its AST."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        # If code has syntax errors, return it unchanged
        return code

    analyzer = CodeAnalyzer()
    analyzer.visit(tree)

    # Missing imports to add
    missing_imports = []

    # Check for typing imports
    needs_typing = False
    typing_imports = set()

    for name in analyzer.used_names:
        if name in TYPING_TYPES and name not in analyzer.defined_names:
            if "typing" not in analyzer.imported_names and not any(
                module == "typing" and name in imports
                for module, imports in analyzer.from_imports.items()
            ):
                needs_typing = True
                typing_imports.add(name)

    # Check for common classes
    for name, module in COMMON_CLASSES.items():
        if name in analyzer.used_names and name not in analyzer.defined_names:
            if module not in analyzer.imported_names and not any(
                mod == module and name in imports for mod, imports in analyzer.from_imports.items()
            ):
                # Use direct import statement if available, otherwise use generic import
                if name in DIRECT_IMPORTS:
                    missing_imports.append(DIRECT_IMPORTS[name])
                else:
                    missing_imports.append(f"import {module}")

    # Add typing imports if needed
    if needs_typing:
        if typing_imports:
            missing_imports.append(f"from typing import {', '.join(sorted(typing_imports))}")
        else:
            missing_imports.append("import typing")

    # If any imports need to be added, add them at the top of the file
    if missing_imports:
        return "\n".join(missing_imports) + "\n\n" + code

    return code
