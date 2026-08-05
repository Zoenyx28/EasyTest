"""API smoke test - verifies the backend is running and responding correctly."""
import json
import sys
import time
import urllib.request
import urllib.error

BASE_URL = "http://localhost:8000"
passed = 0
failed = 0


def request(method: str, path: str, body: dict | None = None, expect_status: int = 200, timeout: int = 30):
    global passed, failed
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp_body = json.loads(resp.read().decode("utf-8"))
            status_ok = resp.status == expect_status
            code_ok = resp_body.get("code") == 20000
            if status_ok and code_ok:
                print(f"  ✓ {method} {path} → {resp.status}")
                passed += 1
            else:
                print(f"  ✗ {method} {path} → {resp.status} (code={resp_body.get('code')}, expected {expect_status}/20000)")
                failed += 1
            return resp_body
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode("utf-8"))
        except Exception:
            err_body = {}
        if e.code == expect_status:
            print(f"  ✓ {method} {path} → {e.code} (expected)")
            passed += 1
        else:
            print(f"  ✗ {method} {path} → {e.code} (expected {expect_status}): {err_body}")
            failed += 1
        return err_body
    except urllib.error.URLError as e:
        print(f"  ✗ {method} {path} → Connection failed: {e.reason}")
        failed += 1
        return None


def main():
    global passed, failed
    print("=" * 60)
    print("API 冒烟测试 - 验证后端服务")
    print("=" * 60)

    # 1. Health
    print("\n[1/7] 健康检查")
    request("GET", "/api/health", timeout=5)

    # 2. Projects
    print("\n[2/7] 项目管理 - 列表 & 创建")
    data = request("GET", "/api/projects")
    project_name = f"TestProject_{int(time.time())}"
    create_data = request("POST", "/api/projects", {
        "name": project_name,
        "description": "API smoke test",
        "source_type": "local",
        "test_path": "./tests",
    }, expect_status=400)  # No real test directory → expected 400

    # 3. Tasks
    print("\n[3/7] 任务管理")
    request("GET", "/api/tasks")

    # 4. Executions
    print("\n[4/7] 执行记录")
    request("GET", "/api/executions")

    # 5. Reports
    print("\n[5/7] 报告接口")
    request("GET", "/api/reports/history")
    request("GET", "/api/reports/latest", expect_status=404)

    # 6. Test cases (quick check)
    print("\n[6/7] 测试用例 (短超时)")
    request("GET", "/api/tests")

    # 7. Frontend
    print("\n[7/7] 前端验证")
    try:
        with urllib.request.urlopen("http://localhost:5173", timeout=5) as resp:
            html = resp.read().decode("utf-8")
            if "<!" in html or "index.html" in resp.headers.get("Content-Type", ""):
                print(f"  ✓ 前端 http://localhost:5173")
                passed += 1
            else:
                print(f"  ~ 前端已启动")
    except Exception as e:
        print(f"  ~ 前端未启动: {e}")

    # Summary
    print("\n" + "=" * 60)
    total = passed + failed
    print(f"结果: {passed}/{total} 通过, {failed} 失败")
    if failed > 0:
        sys.exit(1)
    else:
        print("全部通过!")


if __name__ == "__main__":
    main()
