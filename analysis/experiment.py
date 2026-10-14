from pathlib import Path
import json
import pandas as pd

def write_experiment_results(output_dir, rows, metadata=None):
    """Save one row per phase/protocol as CSV plus experiment metadata JSON."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows)
    csv_path = out / "experiment_metrics.csv"
    json_path = out / "experiment_metadata.json"
    df.to_csv(csv_path, index=False)
    json_path.write_text(json.dumps(metadata or {}, indent=2), encoding="utf-8")
    return str(csv_path), str(json_path)
