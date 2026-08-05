"""运行全部测试用例"""
import subprocess
import sys

if __name__ == "__main__":
    args = [
        sys.executable, "-m", "pytest",
        "-v", "--tb=short",
    ] + sys.argv[1:]
    sys.exit(subprocess.call(args))
