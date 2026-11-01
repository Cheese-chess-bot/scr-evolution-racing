#the sd card 👍😎😂😂
#on a serious note this is what loads new or prev trained models
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

MODELS = Path("models")


def inventory():
    result = []

    for file in sorted(MODELS.glob("*.json")):
        if file.name == "catalog.json":
            continue

        try:
            data = json.loads(
                file.read_text(encoding="utf-8")
            )
        except (OSError, ValueError):
            continue

        if not isinstance(data, dict):
            continue

        fuel_file = MODELS / "fuel" / file.name
        fuel = {}

        if fuel_file.exists():
            try:
                fuel = json.loads(
                    fuel_file.read_text(encoding="utf-8")
                )
            except (OSError, ValueError):
                pass

        best = data.get("best_time")
        if not isinstance(best, (int, float)):
            best = None
        elif best >= 1e8:
            best = None

        result.append({
            "track": data.get("track", file.stem),
            "model_file": file.as_posix(),
            "best_seconds": best,
            "sectors": len(data.get("best_line", {})),
            "total_laps": data.get("total_laps", 0),
            "clean_laps": data.get("clean_laps", 0),
            "fuel_per_lap_litres": fuel.get("fuel_per_lap")
        })

    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "command",
        choices=["list", "commit", "show"]
    )
    parser.add_argument("track", nargs="?")
    args = parser.parse_args()

    tracks = inventory()

    if args.command == "commit":
        MODELS.mkdir(parents=True, exist_ok=True)

        path = MODELS / "catalog.json"
        path.write_text(
            json.dumps({
                "updated_at_utc": datetime.now(
                    timezone.utc
                ).isoformat(),
                "trained_track_count": len(tracks),
                "tracks": tracks
            }, indent=2, allow_nan=False),
            encoding="utf-8"
        )

        print(f"Saved {len(tracks)} tracks to {path}")

    elif args.command == "show":
        found = [
            item for item in tracks
            if args.track and (
                item["track"].lower() == args.track.lower()
                or Path(item["model_file"]).stem.lower()
                == args.track.lower()
            )
        ]
        print(json.dumps(found, indent=2))

    else:
        if not tracks:
            print("No saved tracks yet.")

        for item in tracks:
            print(
                f"{item['track']} | "
                f"best={item['best_seconds']}s | "
                f"sectors={item['sectors']} | "
                f"laps={item['total_laps']} | "
                f"fuel/lap={item['fuel_per_lap_litres']}"
            )


if __name__ == "__main__":
    main()
