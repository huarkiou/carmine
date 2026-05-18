"""CLI entry point for database-based data collection.

Usage:
    uv run python -m src.fetch_to_db sales [--months N]
    uv run python -m src.fetch_to_db specs [--mode {sales|all}]
    uv run python -m src.fetch_to_db all   [--months N]
"""
import argparse
import sys

from .db import init_db
from .pipeline.sales import run as run_sales
from .pipeline.specs import run as run_specs


def main():
    parser = argparse.ArgumentParser(description="Collect automotive data into SQLite database")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sales = sub.add_parser("sales", help="Collect monthly sales rankings")
    p_sales.add_argument("--months", type=int, default=6, choices=range(1, 7),
                         help="Number of recent months (1-6, default 6)")

    p_specs = sub.add_parser("specs", help="Collect config specs")
    p_specs.add_argument("--mode", choices=["sales", "all"], default="sales",
                         help="sales=hot-selling series, all=all brands (default sales)")

    p_all = sub.add_parser("all", help="Collect both sales and specs")
    p_all.add_argument("--months", type=int, default=6, choices=range(1, 7),
                       help="Number of recent months for sales (1-6, default 6)")

    args = parser.parse_args()
    conn = init_db("carmine.db")

    try:
        if args.command == "sales":
            run_sales(conn, months=args.months)
        elif args.command == "specs":
            run_specs(conn, mode=args.mode)
        elif args.command == "all":
            run_sales(conn, months=args.months)
            run_specs(conn, mode="sales")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
