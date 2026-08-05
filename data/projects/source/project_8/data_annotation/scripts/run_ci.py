#!/usr/bin/env python3
"""CI流水线执行脚本

功能：
- 环境检查与依赖安装
- 配置环境变量
- 执行API自动化测试
- 生成Allure测试报告
- 输出测试结果统计
- 返回正确的退出码用于CI判断

使用方式：
    # 执行全部测试
    python run_ci.py

    # 执行指定模块测试
    python run_ci.py --module project

    # 执行冒烟测试
    python run_ci.py --smoke

    # 指定测试环境
    python run_ci.py --env test

    # 生成报告但不启动服务
    python run_ci.py --report-only
"""
import os
import sys
import argparse
import subprocess
import json
from datetime import datetime


# 支持直接运行和导入
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def parse_args():
    parser = argparse.ArgumentParser(description="API自动化测试CI执行脚本")
    parser.add_argument(
        "--module",
        choices=["project", "task", "batch", "all"],
        default="all",
        help="指定测试模块: project/task/batch/all"
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="执行冒烟测试"
    )
    parser.add_argument(
        "--env",
        choices=["test", "staging", "prod"],
        default="test",
        help="指定测试环境: test/staging/prod"
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="仅生成报告，不执行测试"
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="遇到失败立即停止"
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=0,
        help="失败重试次数"
    )
    return parser.parse_args()


def setup_env(env: str):
    os.environ["ENV"] = env
    os.environ["TEST_ENV"] = env
    print(f"[INFO] 环境已设置为: {env}")


def install_dependencies():
    print("[INFO] 检查并安装依赖...")
    result = subprocess.run(
        ["pip", "install", "-r", "requirements.txt", "--quiet"],
        capture_output=True,
        text=True
    )
    if result.returncode != 0:
        print(f"[ERROR] 依赖安装失败: {result.stderr}")
        sys.exit(1)
    print("[INFO] 依赖安装完成")


def run_tests(module: str, smoke: bool, fail_fast: bool, retries: int) -> int:
    cmd = ["python", "-m", "pytest"]

    if smoke:
        cmd.extend(["-m", "smoke"])
    elif module != "all":
        if module == "project":
            cmd.append("api/test_cases/test_project.py")
        elif module == "task":
            cmd.append("api/test_cases/test_task.py")
        elif module == "batch":
            cmd.append("api/test_cases/test_batch.py")

    if fail_fast:
        cmd.append("-x")

    if retries > 0:
        cmd.extend(["--reruns", str(retries), "--reruns-delay", "2"])

    cmd.extend([
        "--alluredir=./reports/allure-results",
        "--clean-alluredir",
        "-v",
        "--tb=short",
        "--junitxml=./reports/junit.xml"
    ])

    print(f"[INFO] 执行命令: {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    print("\n" + "=" * 60)
    print("测试执行输出:")
    print("=" * 60)
    print(result.stdout)
    if result.stderr:
        print("\n[STDERR]:")
        print(result.stderr)

    return result.returncode


def generate_allure_report():
    print("\n[INFO] 生成Allure测试报告...")

    os.makedirs("./reports/allure-report", exist_ok=True)

    result = subprocess.run(
        ["allure", "generate", "./reports/allure-results", "-o", "./reports/allure-report", "--clean"],
        capture_output=True,
        text=True
    )

    if result.returncode != 0:
        print(f"[WARNING] Allure报告生成失败: {result.stderr}")
        return False

    print("[INFO] Allure报告生成成功")
    print(f"[INFO] 报告路径: {os.path.abspath('./reports/allure-report')}")
    return True


def generate_html_report():
    """生成自定义 HTML 测试报告"""
    print("\n[INFO] 生成自定义 HTML 测试报告...")
    try:
        from generate_report import build_report_data, generate_report as gen_html_report, save_history
    except ImportError:
        print("[WARNING] 无法导入 generate_report 模块，使用桩函数替代")
        def build_report_data():
            return None
        def gen_html_report(data):
            pass
        def save_history(data):
            pass

    data = build_report_data()
    if not data:
        print("[WARNING] 未找到测试结果数据，跳过 HTML 报告生成")
        return False

    gen_html_report(data)
    save_history(data)
    filename = os.path.abspath('reports/test_report.html')
    print(f"[INFO] HTML 测试报告生成成功: {filename}")
    return True


def analyze_results():
    results_file = "./reports/allure-results/result.json"
    if not os.path.exists(results_file):
        print("[WARNING] 未找到测试结果文件")
        return None

    with open(results_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    status = data.get("status", {})
    total = sum(status.values())
    passed = status.get("passed", 0)
    failed = status.get("failed", 0)
    skipped = status.get("skipped", 0)

    print("\n" + "=" * 60)
    print("测试结果统计:")
    print("=" * 60)
    print(f"  总用例数: {total}")
    print(f"  通过: {passed}")
    print(f"  失败: {failed}")
    print(f"  跳过: {skipped}")

    if total > 0:
        rate = (passed / total) * 100
        print(f"  通过率: {rate:.2f}%")

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped
    }


def main():
    args = parse_args()

    print("\n" + "=" * 60)
    print("API自动化测试CI执行脚本")
    print("=" * 60)
    print(f"执行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试模块: {args.module}")
    print(f"测试环境: {args.env}")
    print(f"冒烟测试: {'是' if args.smoke else '否'}")
    print(f"立即失败: {'是' if args.fail_fast else '否'}")
    print(f"重试次数: {args.retries}")
    print("=" * 60)

    os.makedirs("./reports", exist_ok=True)

    if not args.report_only:
        setup_env(args.env)
        install_dependencies()

        exit_code = run_tests(args.module, args.smoke, args.fail_fast, args.retries)

        if exit_code != 0:
            print(f"\n[ERROR] 测试执行失败，退出码: {exit_code}")

        generate_allure_report()
        generate_html_report()
        analyze_results()

        sys.exit(exit_code)
    else:
        generate_allure_report()
        generate_html_report()
        analyze_results()
        sys.exit(0)


if __name__ == "__main__":
    main()
