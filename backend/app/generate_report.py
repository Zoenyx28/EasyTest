"""Stub for generate_report - Allure-based report generation.

Originally located at the project root, this module reads Allure results and
builds report data structures. The original source was lost; this stub allows
the backend to function without it. The /api/reports/latest endpoint will
return 404 unless a real generate_report.py is provided.
"""


def build_report_data():
    """Build report data from most recent Allure results.

    Returns None when this stub is active (no real Allure report generated).
    """
    return None


def generate_report(data):
    """Generate HTML report from report data. No-op in stub."""
    return None


def main():
    """CLI entry point."""
    print("[generate_report] Stub active - no real report generated.")
