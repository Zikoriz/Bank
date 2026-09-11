"""Run the Day 7 reporting demonstration.

Usage: ``python -m day7.main --output reports``
"""

from __future__ import annotations

import argparse
from pathlib import Path

from day6.main import run_demo as run_day6_demo
from .report_builder import ReportBuilder


def build_reports(output_dir: str | Path = "reports"):
    """Execute the existing scenario and write the reporting artefacts."""
    source = run_day6_demo(verbose=False)
    builder = ReportBuilder(source["bank"], source["transactions"], source["risk_analyzer"])
    output = Path(output_dir)
    bank = builder.bank_report()
    client = builder.client_report("C001")
    risk = builder.risk_report()
    for name, report in (("bank", bank), ("client_C001", client), ("risk", risk)):
        builder.export_to_json(report, output / f"{name}.json")
        builder.export_to_csv(report, output / f"{name}.csv")
    builder.create_bank_charts()
    builder.create_client_charts("C001")
    builder.create_risk_charts()
    charts = builder.save_charts(output / "charts")
    return {"bank": bank, "client": client, "risk": risk, "charts": charts}


def main():
    parser = argparse.ArgumentParser(description="Day 7 banking reports")
    parser.add_argument("--output", type=Path, default=Path("reports"))
    args = parser.parse_args()
    result = build_reports(args.output)
    print(f"Saved {len(result['charts'])} charts to {args.output}")


if __name__ == "__main__":
    main()
