"""Summarise the SQLite snapshot and draw ordered distributions with denominators."""
import sqlite3
from contextlib import closing

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from .common import write_json
from .validator import RATINGS


def analyse(output):
    with closing(sqlite3.connect(output / "output.db")) as connection:
        frame = pd.read_sql_query("SELECT * FROM establishments ORDER BY fhrs_id", connection)
    figures = output / "figures"
    figures.mkdir(exist_ok=True)
    frame.describe(include="all").to_csv(output / "descriptive_statistics.csv")
    frame.dtypes.astype(str).to_csv(output / "data_types.csv", header=["dtype"])
    frame.groupby(["authority", "business_type"]).agg(
        records=("fhrs_id", "size"), rated=("rating_numeric", "count"),
        median_rating=("rating_numeric", "median"), median_score_total=("score_total", "median")
    ).to_csv(output / "grouped_statistics.csv")
    counts = frame.pivot_table(index="authority", columns="rating_value", values="fhrs_id", aggfunc="count", fill_value=0)
    counts = counts.reindex(columns=RATINGS, fill_value=0)
    counts.to_csv(output / "ratings_pivot.csv")
    proportions = counts.div(counts.sum(axis=1), axis=0) * 100
    proportions.to_csv(output / "ratings_percent.csv")
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})
    palette = ["#9d2437", "#cd4c43", "#e38c4a", "#ddc26a", "#80b4a0", "#2d7e78", "#788cae", "#b2b6be", "#d0c6b6"]
    ax = proportions.plot.barh(stacked=True, figsize=(11, 4.6), color=palette, width=0.55)
    ax.set(title="Food hygiene ratings and statuses by authority", xlabel="Share of all listed establishments (%)", ylabel="")
    ax.set_xlim(0, 100)
    ax.set_yticklabels([f"{name} (n={int(counts.loc[name].sum()):,})" for name in counts.index])
    ax.legend([x.replace("Awaiting", "Awaiting ") for x in RATINGS], loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=5, frameon=False)
    ax.figure.tight_layout()
    ax.figure.savefig(figures / "01_ratings_by_authority.png", dpi=160, bbox_inches="tight")
    plt.close(ax.figure)

    rated = frame.loc[frame.rating_numeric.notna()].copy()
    rated["low_rating"] = np.where(rated.rating_numeric < 3, 1, 0)
    by_type = rated.groupby("business_type").agg(rated=("fhrs_id", "size"), low=("low_rating", "sum"))
    by_type["low_percent"] = 100 * by_type.low / by_type.rated
    by_type.to_csv(output / "business_type_low_ratings.csv")
    displayed = by_type.loc[by_type.rated >= 30].sort_values("low_percent")
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.barh(displayed.index, displayed.low_percent, color="#326b8e")
    for i, (_, row) in enumerate(displayed.iterrows()):
        ax.text(row.low_percent + 0.15, i, f"{row.low_percent:.1f}% (n={int(row.rated):,})", va="center", fontsize=9)
    maximum = float(displayed.low_percent.max()) if len(displayed) else 1
    ax.set_xlim(0, max(5, maximum * 1.55))
    ax.set(title="Share rated 0-2 by business type", xlabel="Percent of numerically rated establishments", ylabel="")
    fig.text(0.02, 0.01, "Leeds and York combined; types with at least 30 numeric ratings. Descriptive, not adjusted for authority mix.", fontsize=9)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(figures / "02_low_ratings_by_type.png", dpi=160, bbox_inches="tight")
    plt.close(fig)

    columns = ["hygiene", "structural", "management"]
    medians = rated.groupby("rating_numeric")[columns].median().reindex(range(6))
    medians.to_csv(output / "score_medians_by_rating.csv")
    score_counts = rated.groupby("rating_numeric")[columns].count().reindex(range(6), fill_value=0)
    score_counts.to_csv(output / "score_counts_by_rating.csv")
    ax = medians.plot.bar(figsize=(10, 5), color=["#326b8e", "#cd8849", "#68875c"])
    ax.set(title="Median intervention scores by overall hygiene rating", xlabel="Overall rating (higher means better compliance)",
           ylabel="Median component score (higher means worse compliance)")
    ax.tick_params(axis="x", rotation=0)
    ax.legend(["Hygiene", "Structure", "Management"], frameon=False)
    ax.figure.tight_layout()
    ax.figure.savefig(figures / "03_component_scores.png", dpi=160, bbox_inches="tight")
    plt.close(ax.figure)

    findings = []
    for name in counts.index:
        n = int(counts.loc[name].sum())
        rated_n = int(counts.loc[name, [str(i) for i in range(6)]].sum())
        five = int(counts.loc[name, "5"])
        findings.append(f"{name}: {five:,}/{n:,} listed establishments ({100*five/n:.1f}%) have rating 5; {rated_n:,} have numeric ratings.")
    if len(displayed):
        top = displayed.iloc[-1]
        findings.append(f"Among business types with at least 30 rated records, {displayed.index[-1]} has the highest observed share rated 0-2: {int(top.low)}/{int(top.rated)} ({top.low_percent:.1f}%). This comparison is unadjusted.")
    available = medians.dropna(how="all")
    if len(available) >= 2:
        first, last = available.index[0], available.index[-1]
        findings.append(f"At ratings {int(first)} and {int(last)}, median hygiene scores are {medians.loc[first, 'hygiene']:g} and {medians.loc[last, 'hygiene']:g}. Component scores help determine overall ratings, so this association is not independent causal evidence.")
    summary = {"rows": len(frame), "columns": len(frame.columns), "numeric_ratings": len(rated),
               "business_types": int(frame.business_type.nunique()), "findings": findings,
               "limitations": ["A current listing snapshot, not inspection histories or a representative UK sample.",
                               "Authority comparisons may reflect business mix and inspection timing.",
                               "Special statuses remain in status distributions but are excluded from numeric rating denominators.",
                               "1901 dates are flagged and excluded from date arithmetic; the source strings remain stored."]}
    write_json(output / "analysis.json", summary)
    (output / "findings.md").write_text("# Measured findings\n\n" + "\n\n".join(findings + summary["limitations"]), encoding="utf-8")
    return summary
