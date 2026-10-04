"""반복별 데이터와 표본 통계 보존. 단일 반복에서는 SEM을 추정하지 않음."""

import csv
import json
from collections import defaultdict
from math import sqrt
from pathlib import Path
from statistics import mean, stdev


def summarize(rows, group_fields, metrics):
    groups = defaultdict(list)
    for row in rows:
        groups[tuple(row[field] for field in group_fields)].append(row)
    summaries = []
    for key, samples in groups.items():
        result = dict(zip(group_fields, key))
        result["trials"] = len(samples)
        for metric in metrics:
            values = [row[metric] for row in samples if row[metric] is not None]
            deviation = stdev(values) if len(values) > 1 else None
            result.update(
                {
                    f"{metric}_n": len(values),
                    f"{metric}_mean": mean(values) if values else None,
                    f"{metric}_std": deviation,
                    f"{metric}_sem": deviation / sqrt(len(values))
                    if deviation is not None
                    else None,
                }
            )
        summaries.append(result)
    return summaries


def write_csv(path, rows):
    with Path(path).open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    key: json.dumps(value) if isinstance(value, (list, dict)) else value
                    for key, value in row.items()
                }
            )
