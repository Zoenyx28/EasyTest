import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

pytest_plugins = [
    'fixtures.api_fixture',
    'fixtures.common_fixture',
]

def pytest_configure(config):
    config.addinivalue_line('markers', 'api: API测试')
    config.addinivalue_line('markers', 'ui: UI测试')
    config.addinivalue_line('markers', 'smoke: 冒烟测试')
    config.addinivalue_line('markers', 'login: 登录相关测试')