#i hate scr bro
#not that much but yah
#bro like we ge all the data and shit and somehow we cant ask for a pitstop👏👏👏👏
#still les add it
#why? coz i want to make a strategy brd 👍
import json
import re
from pathlib import Path


class PitPlanner:
    def __init__(self, track, race_laps=10, model_dir="models"):
        slug = re.sub(
            r"[^a-z0-9_-]+", "_", track.lower()
        )[:80]

        self.path = (
            Path(model_dir) / "fuel" / f"{slug}.json"
        )
        self.path.parent.mkdir(
            parents=True, exist_ok=True
        )

        self.race_laps = race_laps
        self.fuel_per_lap = None
        self.lap_start_fuel = None
        self.last_fuel = None
        self.last_lap = 0
        self.alert_level = 0

        if self.path.exists():
            try:
                data = json.loads(
                    self.path.read_text(encoding="utf-8")
                )
                value = data.get("fuel_per_lap")
                if isinstance(value, (int, float)) and value > 0:
                    self.fuel_per_lap = float(value)
                    print(
                        f"Loaded fuel model: "
                        f"{value:.3f} L/lap"
                    )
            except (ValueError, TypeError, OSError):
                print("Fuel model invalid; measuring again.")

    def save(self):
        if self.fuel_per_lap is None:
            return

        temp = self.path.with_suffix(".tmp")
        temp.write_text(
            json.dumps({
                "fuel_per_lap": round(
                    self.fuel_per_lap, 5
                ),
                "pit_service_supported": False
            }, indent=2),
            encoding="utf-8"
        )
        temp.replace(self.path)

    def update(self, state, completed_laps):
        if "fuel" not in state:
            return

        fuel = float(state["fuel"])

        if self.lap_start_fuel is None:
            self.lap_start_fuel = fuel

        if (
            self.last_fuel is not None
            and fuel > self.last_fuel + 0.25
        ):
            print("Refuelling detected.")
            self.lap_start_fuel = fuel
            self.alert_level = 0

        if completed_laps > self.last_lap:
            consumed = self.lap_start_fuel - fuel

            if 0.05 < consumed < 20:
                if self.fuel_per_lap is None:
                    self.fuel_per_lap = consumed
                else:
                    self.fuel_per_lap = (
                        0.7 * self.fuel_per_lap
                        + 0.3 * consumed
                    )

                self.save()

                print(
                    f"FUEL: {consumed:.2f} L this lap | "
                    f"Average {self.fuel_per_lap:.2f} L/lap"
                )

            self.lap_start_fuel = fuel
            self.last_lap = completed_laps

        self.last_fuel = fuel

        if self.fuel_per_lap is None:
            return

        remaining = max(
            0, self.race_laps - completed_laps
        )
        estimated_range = fuel / self.fuel_per_lap

        if remaining <= 0:
            return

        if estimated_range < 1.3 and self.alert_level < 2:
            print(
                "CRITICAL FUEL: Under ~1.3 laps of "
                "estimated fuel left. Standard SCR "
                "cannot perform actual pit service!"
            )
            self.alert_level = 2

        elif (
            fuel < (remaining + 0.5) * self.fuel_per_lap
            and estimated_range < 2.3
            and self.alert_level < 1
        ):
            print(
                "PIT NEEDED SOON: Insufficient fuel "
                "for the remaining race. This is an "
                "alert, not an actual pit request."
            )
            self.alert_level = 1
