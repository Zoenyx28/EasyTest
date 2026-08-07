"""AST-based step extractor for test functions (integrated into the system).

Parses the source code of test functions to extract API calls and
assertion calls as structured steps. No pytest dependency.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional


class StepExtractor:
    """Extracts steps from test function source code using AST analysis."""

    def __init__(
        self,
        api_client_prefixes: Optional[List[str]] = None,
        assertion_methods: Optional[List[str]] = None,
        api_desc_map: Optional[Dict[str, str]] = None,
    ):
        self.api_client_prefixes = api_client_prefixes or [
            "api_client",
            "http_client",
            "client",
        ]
        self.assertion_methods = assertion_methods or [
            "assert_equal",
            "assert_true",
            "assert_false",
            "assert_status_code",
            "assert_jsonpath_value",
            "assert_response",
            "assert_response_time",
            "assert_pagination",
            "assert_response_success",
            "assert_not_equal",
            "assert_contains",
            "assert_not_contains",
            "assert_length",
            "assert_greater_than",
            "assert_less_than",
            "assert_is_not_none",
            "assert_is_none",
            "assert_json_schema",
            "assert_list_length",
        ]
        # method name -> Chinese description (from API wrapper docstrings)
        self.api_desc_map = api_desc_map or {}
        # Current module tree (for helper inlining) + helper function index
        self._tree: Optional[ast.Module] = None
        self._helpers: Dict[str, ast.FunctionDef] = {}

    def _build_helpers(self, tree: ast.Module) -> None:
        """Index module-level helper functions (non-test functions) so that
        bare calls like ``_create_batch_as_pm(...)`` can be inlined as steps."""
        self._tree = tree
        self._helpers = {}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                name = node.name
                if not name.startswith('test'):
                    self._helpers[name] = node

    def extract_from_source(self, source_code: str) -> List[Dict[str, str]]:
        """Extract steps from source code string."""
        try:
            tree = ast.parse(source_code)
        except SyntaxError:
            return []
        self._build_helpers(tree)
        return self._extract_from_tree(tree, target_func=None, class_name=None)

    def extract_from_file(
        self, file_path: Path, func_name: str, class_name: Optional[str] = None
    ) -> List[Dict[str, str]]:
        """Extract steps from a specific function in a file."""
        try:
            source = file_path.read_text(encoding="utf-8")
        except Exception:
            return []
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return []
        self._build_helpers(tree)
        return self._extract_from_tree(tree, target_func=func_name, class_name=class_name)

    def extract_from_file_all(
        self, file_path: Path
    ) -> Dict[str, List[Dict[str, str]]]:
        """Extract steps for all test functions in a file.

        Returns a dict mapping 'ClassName::method_name' (or 'method_name' for
        module-level functions) -> list of steps.
        """
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except Exception:
            return {}
        self._build_helpers(tree)

        result: Dict[str, List[Dict[str, str]]] = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        steps = self._extract_from_function_body(sub)
                        if steps:
                            result[f"{node.name}::{sub.name}"] = steps
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                steps = self._extract_from_function_body(node)
                if steps:
                    result[node.name] = steps
        return result

    def _extract_from_tree(
        self,
        tree: ast.Module,
        target_func: Optional[str],
        class_name: Optional[str],
    ) -> List[Dict[str, str]]:
        """Extract steps from the AST tree for a specific function."""
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                if class_name and node.name != class_name:
                    continue
                for sub in node.body:
                    if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if target_func and sub.name != target_func:
                            continue
                        steps = self._extract_from_function_body(sub)
                        if steps:
                            return steps
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if target_func and node.name != target_func:
                    continue
                steps = self._extract_from_function_body(node)
                if steps:
                    return steps
        return []

    def _extract_from_function_body(
        self, func_node: ast.FunctionDef
    ) -> List[Dict[str, str]]:
        """Extract steps from a function definition AST node, preserving order."""
        steps: List[Dict[str, str]] = []

        # ast.walk does NOT preserve order. Walk the body sequentially.
        def _walk_body(body_nodes):
            for node in body_nodes:
                if isinstance(node, ast.FunctionDef):
                    continue  # Skip nested function defs
                steps.extend(self._extract_step_list(node))
                # Walk children for non-step nodes that might contain steps
                for child in ast.iter_child_nodes(node):
                    if isinstance(child, (ast.Expr, ast.Assign)):
                        steps.extend(self._extract_step_list(child))

        _walk_body(func_node.body)
        return steps

    def _extract_step_list(self, node: ast.AST) -> List[Dict[str, str]]:
        """Extract all steps produced by a node (0, 1, or more if a helper
        function is inlined)."""
        # Bare helper call: _create_batch_as_pm(...) -> inline helper steps
        for target in (node,):
            if isinstance(target, ast.Assign):
                value = target.value
            elif isinstance(target, ast.Expr):
                value = target.value
            else:
                continue
            if isinstance(value, ast.Await):
                value = value.value
            if isinstance(value, ast.Call) and isinstance(value.func, ast.Name):
                helper_steps = self._helper_steps(value.func.id)
                if helper_steps:
                    return helper_steps
        step = self._extract_step(node)
        return [step] if step else []

    def _helper_steps(
        self,
        name: str,
        depth: int = 0,
        visited: Optional[set] = None,
    ) -> List[Dict[str, str]]:
        """Inline the steps of a module-level helper function (recursive,
        cycle-safe). Calls are ordered by source line number."""
        if depth > 3 or name not in self._helpers:
            return []
        visited = visited or set()
        if name in visited:
            return []
        visited = visited | {name}
        func_node = self._helpers[name]

        calls = [n for n in ast.walk(func_node) if isinstance(n, ast.Call)]
        calls.sort(key=lambda c: (c.lineno, c.col_offset))

        steps: List[Dict[str, str]] = []
        for c in calls:
            if isinstance(c.func, ast.Attribute):
                step = self._extract_from_call(c)
                if step and (not steps or steps[-1] != step):
                    steps.append(step)
            elif isinstance(c.func, ast.Name) and c.func.id in self._helpers:
                steps.extend(self._helper_steps(c.func.id, depth + 1, visited))
        return steps

    def _extract_step(self, node: ast.AST) -> Optional[Dict[str, str]]:
        """Extract a single step from an AST node, if applicable."""
        # Handle: response = await api_client.post(...)  (Assign, async or sync)
        if isinstance(node, ast.Assign):
            value = node.value
            if isinstance(value, ast.Await):
                value = value.value
            if isinstance(value, ast.Call):
                return self._extract_from_call(value)
            return None

        # Handle: await api_client.post(...)  (standalone Expr)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Await):
            call = node.value.value
            if isinstance(call, ast.Call):
                return self._extract_from_call(call)
            return None

        # Handle: assertion.assert_response(...)  (non-awaited standalone Expr)
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            return self._extract_from_call(node.value)

        return None

    def _extract_from_call(self, call: ast.Call) -> Optional[Dict[str, str]]:
        """Extract step info from a Call AST node."""
        func = call.func

        if not isinstance(func, ast.Attribute):
            return None

        obj_name = getattr(func.value, "id", None) if isinstance(func.value, ast.Name) else None
        method_name = func.attr

        if obj_name is None:
            return None

        # 1) Assertion call: assertion.assert_xxx(...)
        if obj_name == "assertion" and method_name in self.assertion_methods:
            return self._extract_assertion(call, method_name)

        # 2) api_client / http_client / client direct calls
        if obj_name in self.api_client_prefixes:
            return self._extract_api_call(call, method_name, obj_name)

        # 3) Any awaited obj.method() call that is not a fixture or data setup
        _skip_names = {"self", "cls", "super", "logger", "case_data", "request",
                       "resp", "response", "res", "data", "resp_json",
                       "response_json", "result", "results", "body", "content",
                       "faker_data", "random_data", "gen_data", "config",
                       "settings", "env_handler", "os", "sys", "time",
                       "datetime", "json", "yaml", "re"}
        _data_methods = {"get", "json", "text", "format", "append", "copy",
                         "split", "strip", "lower", "upper", "update", "pop",
                         "items", "keys", "values", "count", "clear", "extend",
                         "replace", "join", "read", "close"}
        if obj_name not in _skip_names and method_name not in _data_methods:
            return self._extract_api_call(call, method_name, obj_name)

        return None

    def _extract_api_call(self, call: ast.Call, method_name: str, obj_name: str) -> Dict[str, str]:
        """Extract a readable API step: 调用xxx接口，引入xxx参数（接口中文描述）."""
        params = self._summarize_params(call)
        desc = self.api_desc_map.get(method_name, "")
        text = f"调用{method_name}接口"
        if params:
            text += f"，引入{params}"
        if desc:
            text += f"（{desc}）"
        return {
            "type": "api",
            "description": text,
            "code": f"{obj_name}.{method_name}",
            "method": method_name,
            "params": params,
            "desc": desc,
        }

    def _extract_assertion(self, call: ast.Call, method_name: str) -> Dict[str, str]:
        """Extract a readable assertion step: 断言xxx描述（预期: xxx ==(!=)xxx 实际）."""
        args = call.args
        # Last string constant arg is usually the human-readable msg
        # (supports plain strings and simple f-strings like f"{prefix}创建成功")
        msg = ""
        if args and isinstance(args[-1], (ast.Constant, ast.JoinedStr)):
            if isinstance(args[-1], ast.Constant) and isinstance(args[-1].value, str):
                msg = args[-1].value
            elif isinstance(args[-1], ast.JoinedStr):
                parts = [v.value for v in args[-1].values
                         if isinstance(v, ast.Constant) and isinstance(v.value, str)]
                msg = "".join(parts)

        expected, actual, op = "", "", ""
        if method_name == "assert_status_code":
            actual = "response.status_code"
            if len(args) >= 2:
                expected = self._fmt_expr(args[1])
            op = "=="
        elif method_name in ("assert_equal", "assert_not_equal",
                             "assert_greater_than", "assert_less_than",
                             "assert_contains", "assert_not_contains"):
            if len(args) >= 2:
                actual = self._fmt_expr(args[0])
                expected = self._fmt_expr(args[1])
            op = {
                "assert_equal": "==",
                "assert_not_equal": "!=",
                "assert_greater_than": ">",
                "assert_less_than": "<",
                "assert_contains": "包含",
                "assert_not_contains": "不包含",
            }.get(method_name, "==")
        elif method_name == "assert_jsonpath_value":
            actual = "response.data"
            if len(args) >= 3:
                expected = self._fmt_expr(args[2])
            op = "=="

        assert_desc = method_name.replace("assert_", "").replace("_", " ")
        text = f"断言{msg or assert_desc}"
        if expected:
            text += f"（预期: {expected} {op} 实际: {actual}）"
        return {
            "type": "assert",
            "description": text,
            "code": f"assertion.{method_name}",
            "expected": expected,
            "actual": actual,
            "operator": op,
        }

    def _summarize_params(self, call: ast.Call) -> str:
        """Summarize call arguments as a compact string, e.g. name=\"x\", data_type=\"image\"."""
        parts: List[str] = []
        for kw in call.keywords:
            if kw.arg is None:
                continue
            parts.append(f"{kw.arg}={self._fmt_expr(kw.value)}")
        for arg in call.args:
            parts.append(self._fmt_expr(arg))
        # Keep the list short for readability
        if len(parts) > 5:
            parts = parts[:5] + ["..."]
        return ", ".join(parts)

    def _fmt_expr(self, node: ast.AST) -> str:
        """Render an AST expression as a short readable string."""
        try:
            if isinstance(node, ast.Constant):
                v = node.value
                if isinstance(v, str):
                    return repr(v) if len(v) <= 40 else repr(v[:37] + "...")
                return str(v)
            if isinstance(node, ast.Name):
                return node.id
            if isinstance(node, ast.Subscript):
                base = self._fmt_expr(node.value)
                key = self._fmt_expr(node.slice)
                return f"{base}[{key}]"
            if isinstance(node, ast.Attribute):
                return f"{self._fmt_expr(node.value)}.{node.attr}"
            if isinstance(node, ast.Call):
                return f"{self._fmt_expr(node.func)}(...)"
            if isinstance(node, ast.Await):
                return self._fmt_expr(node.value)
            if isinstance(node, ast.List):
                items = [self._fmt_expr(e) for e in node.elts[:3]]
                return "[" + ", ".join(items) + (", ...]" if len(node.elts) > 3 else "]")
            if isinstance(node, ast.Dict):
                return "{...}"
            if isinstance(node, ast.Tuple):
                items = [self._fmt_expr(e) for e in node.elts[:3]]
                return "(" + ", ".join(items) + (", ...)" if len(node.elts) > 3 else ")")
            if isinstance(node, ast.UnaryOp):
                return f"{ast.unparse(node)[:60]}"
            return ast.unparse(node)[:60] if hasattr(ast, "unparse") else "?"
        except Exception:
            return "?"
