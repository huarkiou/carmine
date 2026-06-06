"""CLI entry point for exporting database data to xlsx.

Usage:
    uv run python -m src.export sales  --months 6 --top 50
    uv run python -m src.export specs
    uv run python -m src.export all
"""

import argparse

from ..db import init_db, DEFAULT_DB
from ..encoding import setup
from .sales import run as run_sales_export
from .specs import run as run_specs_export


def main():
    setup()
    parser = argparse.ArgumentParser(description="Export database data to xlsx")
    sub = parser.add_subparsers(dest="command", required=True)

    p_sales = sub.add_parser("sales", help="Export sales ranking")
    p_sales.add_argument(
        "--months",
        type=int,
        default=6,
        choices=range(1, 7),
        help="Number of recent months (1-6, default 6)",
    )
    p_sales.add_argument(
        "--top", type=int, default=50, help="Top N per sub-category (default 50)"
    )
    p_sales.add_argument(
        "--db", default=DEFAULT_DB, help="Path to input SQLite database"
    )
    p_sales.add_argument(
        "--output", default="output", help="Output directory for xlsx files"
    )

    p_specs = sub.add_parser("specs", help="Export all config specs as xlsx")
    p_specs.add_argument(
        "--db", default=DEFAULT_DB, help="Path to input SQLite database"
    )
    p_specs.add_argument(
        "--output", default="output", help="Output directory for xlsx files"
    )

    p_all = sub.add_parser("all", help="Export both sales and specs (default params)")
    p_all.add_argument(
        "--months",
        type=int,
        default=6,
        choices=range(1, 7),
        help="Number of recent months for sales (1-6, default 6)",
    )
    p_all.add_argument(
        "--top", type=int, default=50, help="Top N per sub-category (default 50)"
    )
    p_all.add_argument(
        "--db", default=DEFAULT_DB, help="Path to input SQLite database"
    )
    p_all.add_argument(
        "--output", default="output", help="Output directory for xlsx files"
    )

    args = parser.parse_args()
    conn = init_db(args.db)

    try:
        if args.command == "sales":
            run_sales_export(conn, months=args.months, top=args.top, output_dir=args.output)
        elif args.command == "specs":
            run_specs_export(conn, output_dir=args.output)
        elif args.command == "all":
            run_sales_export(conn, months=args.months, top=args.top, output_dir=args.output)
            run_specs_export(conn, output_dir=args.output)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
