
"""
SCR EVOLUTION RACING
====================

Track-adaptive racing AI for TORCS SCR.

Features:
- Permanent per-track racing-line memory
- 3 warm-up laps per session
- Cumulative lap and clean-lap statistics
- Best-lap evolutionary learning
- Random racing-line mutations
- Dynamic braking, no fixed speed limit
- Independent steering, throttle and brake
- Experimental drifting
- Opponent detection
- Approximate leader-line tracking
- Automatic gear shifting
- JSON model saving/loading

Requires: scr.py
Python: 3.10+
"""

import json
import math
import random
import re
from pathlib import Path

from scr import ANGLES, array, clamp, sensor


# ==========================================
# CONFIGURATION
# ==========================================

SECTOR_METRES = 25
WARMUP_LAPS = 3

MAX_LINE_OFFSET = 0.60
MUTATION_STD = 0.045
MAX_MUTATION = 0.12

CLEAN_LAP_BAD_TICK_LIMIT = 0.035
MAX_NEW_DAMAGE = 300

MODEL_VERSION = 2


# ==========================================
# AI BRAIN
# ==========================================

class EvoBrain:

    def __init__(self, track_name, output_dir="models"):

        self.track = track_name

        slug = re.sub(
            r"[^a-z0-9_-]+",
            "_",
            track_name.lower()
        ).strip("_")[:80] or "unknown_track"

        self.path = Path(output_dir) / f"{slug}.json"

        self.path.parent.mkdir(
            parents=True,
            exist_ok=True
        )

        # Best learned racing model
        self.best_time = float("inf")
        self.best_line = {}
        self.best_speed = {}

        # Opponent line estimates
        self.ghost_line = {}

        # Session statistics
        self.laps = 0
        self.learning_attempts = 0

        # Lifetime statistics
        self.total_laps = 0
        self.clean_laps = 0

        # Lap detection
        self.prev_dist = None
        self.prev_curtime = None

        # Current lap samples
        self.samples = {}
        self.bad_ticks = 0
        self.total_ticks = 0
        self.start_damage = None

        # Evolution
        self.mutation = {}

        # Load existing track memory
        self.load()

        print("=" * 45)
        print("SCR EVOLUTION BRAIN")
        print(f"TRACK: {self.track}")
        print(f"MEMORY: {self.path}")
        print(f"TOTAL SAVED LAPS: {self.total_laps}")
        print(f"CLEAN LAPS: {self.clean_laps}")
        print(f"WARMUP: {WARMUP_LAPS} laps")

        if math.isfinite(self.best_time):
            print(f"BEST LAP: {self.best_time:.2f}s")
        else:
            print("BEST LAP: Not recorded")

        print("=" * 45)

    # ======================================
    # PERSISTENT MEMORY
    # ======================================

    def load(self):

        if not self.path.exists():
            print(
                f"[MEMORY] New track: {self.track}"
            )
            return

        try:

            data = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )

            value = data.get("best_time")

            if value is not None:
                value = float(value)

                if math.isfinite(value) and value > 0:
                    self.best_time = value

            self.best_line = {
                str(k): float(v)
                for k, v in data.get(
                    "best_line", {}
                ).items()
            }

            self.best_speed = {
                str(k): float(v)
                for k, v in data.get(
                    "best_speed", {}
                ).items()
            }

            self.total_laps = max(
                0,
                int(data.get("total_laps", 0))
            )

            self.clean_laps = max(
                0,
                int(data.get("clean_laps", 0))
            )

            print(
                f"[MEMORY] Loaded {self.track}"
            )

        except (
            ValueError,
            TypeError,
            OSError,
            AttributeError
        ) as error:

            print(
                f"[MEMORY] Load failed: {error}"
            )
            print(
                "[MEMORY] Starting fresh."
            )

    def save(self):

        data = {

            "version": MODEL_VERSION,

            "track": self.track,

            "best_time": (
                self.best_time
                if math.isfinite(self.best_time)
                else None
            ),

            "best_line": self.best_line,

            "best_speed": self.best_speed,

            "total_laps": self.total_laps,

            "clean_laps": self.clean_laps,

            "sector_metres": SECTOR_METRES,

            "warmup_laps": WARMUP_LAPS,

            "learning_method": (
                "Best-lap selection and "
                "sector mutation"
            )

        }

        temp = self.path.with_suffix(".tmp")

        temp.write_text(
            json.dumps(
                data,
                indent=2,
                allow_nan=False
            ),
            encoding="utf-8"
        )

        temp.replace(self.path)

    # ======================================
    # TRACK MEMORY
    # ======================================

    def sector(self, position):

        return str(
            max(
                0,
                int(
                    max(position, 0)
                    // SECTOR_METRES
                )
            )
        )

    def get_target_line(self, distance):

        key = self.sector(distance)

        target = self.best_line.get(
            key, 0.0
        )

        # Mutation is enabled only after
        # the 3 warm-up laps.
        if self.laps >= WARMUP_LAPS:

            target += self.mutation.get(
                key, 0.0
            )

            # Weakly follow observed
            # opponent positions.
            if key in self.ghost_line:

                target = (
                    0.90 * target
                    + 0.10 * self.ghost_line[key]
                )

        return clamp(
            target,
            -MAX_LINE_OFFSET,
            MAX_LINE_OFFSET
        )

    # ======================================
    # SENSOR OBSERVATION
    # ======================================

    def observe(self, s):

        distance = sensor(
            s, "distFromStart"
        )

        current_time = sensor(
            s, "curLapTime"
        )

        last_lap_time = sensor(
            s, "lastLapTime"
        )

        # Detect crossing of start/finish.
        crossed = (

            self.prev_dist is not None

            and self.prev_dist > 100

            and distance < (
                self.prev_dist - 100
            )

            and last_lap_time > 20
        )

        if crossed:

            self.finish_lap(
                last_lap_time,
                sensor(s, "damage")
            )

        self.prev_dist = distance
        self.prev_curtime = current_time

        self.total_ticks += 1

        position = sensor(
            s, "trackPos"
        )

        angle = sensor(
            s, "angle"
        )

        speed = sensor(
            s, "speedX"
        )

        damage = sensor(
            s, "damage"
        )

        if self.start_damage is None:
            self.start_damage = damage

        # Count unstable/off-track ticks.
        if (
            abs(position) > 0.98
            or abs(angle) > 1.15
        ):
            self.bad_ticks += 1

        # Collect racing-line observations.
        if (
            speed > 15
            and abs(position) < 0.95
        ):

            key = self.sector(distance)

            if key not in self.samples:

                self.samples[key] = {
                    "sum_pos": 0.0,
                    "sum_speed": 0.0,
                    "n": 0
                }

            item = self.samples[key]

            item["sum_pos"] += position
            item["sum_speed"] += speed
            item["n"] += 1

        # Learn approximate opponent paths.
        self.observe_opponent(s)

    # ======================================
    # OPPONENT OBSERVATION
    # ======================================

    def observe_opponent(self, s):

        if sensor(
            s, "racePos", 1
        ) <= 1:
            return

        opponents = array(
            s, "opponents", 36
        )

        candidates = [

            (opponents[i], i)

            for i in range(14, 23)

            if 15 < opponents[i] < 65

        ]

        if not candidates:
            return

        distance, index = min(candidates)

        bearing = math.radians(
            (index - 18) * 10
        )

        road = array(
            s, "track", 19
        )

        track_width = clamp(
            road[0] + road[18],
            8,
            25
        )

        approx_position = (

            sensor(s, "trackPos")

            + (
                2
                * math.sin(bearing)
                * distance
                / track_width
            )
        )

        if abs(approx_position) > 0.7:
            return

        future_distance = (

            sensor(
                s, "distFromStart"
            )

            + distance * math.cos(bearing)

        )

        key = self.sector(
            future_distance
        )

        previous = self.ghost_line.get(
            key,
            approx_position
        )

        self.ghost_line[key] = (

            0.9 * previous
            + 0.1 * approx_position

        )

    # ======================================
    # EVOLUTION
    # ======================================

    def generate_mutation(self):

        if not self.best_line:

            self.mutation = {}
            return

        self.mutation = {

            key: clamp(

                random.gauss(
                    0,
                    MUTATION_STD
                ),

                -MAX_MUTATION,
                MAX_MUTATION

            )

            for key in self.best_line

        }

        self.learning_attempts += 1

        print(
            "[EVOLUTION] Candidate "
            f"#{self.learning_attempts} generated"
        )

    # ======================================
    # FINISH LAP
    # ======================================

    def finish_lap(
        self,
        seconds,
        end_damage
    ):

        # Completed laps this session
        self.laps += 1

        # Permanent count across sessions
        self.total_laps += 1

        damage_added = (

            end_damage
            - (
                self.start_damage
                if self.start_damage is not None
                else end_damage
            )

        )

        bad_ratio = (

            self.bad_ticks
            / max(1, self.total_ticks)

        )

        clean = (

            self.total_ticks > 100

            and bad_ratio
            < CLEAN_LAP_BAD_TICK_LIMIT

            and damage_added
            < MAX_NEW_DAMAGE

            and len(self.samples) >= 15

        )

        if clean:
            self.clean_laps += 1

        # Phase detection
        if self.laps <= WARMUP_LAPS:

            phase = "WARMUP"

        else:

            phase = "EVOLUTION"

        print()
        print("=" * 45)

        print(
            f"LAP COMPLETED: {self.laps}"
        )

        print(
            f"PHASE: {phase}"
        )

        print(
            f"TIME: {seconds:.2f}s"
        )

        print(
            f"STATUS: "
            f"{'CLEAN' if clean else 'INVALID'}"
        )

        print(
            f"DAMAGE ADDED: {damage_added:.1f}"
        )

        print(
            f"LIFETIME LAPS: {self.total_laps}"
        )

        print(
            f"LIFETIME CLEAN: {self.clean_laps}"
        )

        # Save new best racing line.
        if clean and seconds < self.best_time:

            self.best_time = seconds

            self.best_line = {

                key: clamp(

                    value["sum_pos"]
                    / value["n"],

                    -0.58,
                    0.58

                )

                for key, value
                in self.samples.items()

                if value["n"] > 0

            }

            self.best_speed = {

                key: (

                    value["sum_speed"]
                    / value["n"]

                )

                for key, value
                in self.samples.items()

                if value["n"] > 0

            }

            print(
                "[EVOLUTION] NEW BEST LAP!"
            )

            print(
                f"[EVOLUTION] Best: "
                f"{self.best_time:.2f}s"
            )

        # Save memory after every completed lap.
        self.save()

        print(
            f"[MEMORY] Saved to {self.path}"
        )

        # Reset current-lap data.
        self.samples = {}

        self.total_ticks = 0

        self.bad_ticks = 0

        self.start_damage = end_damage

        self.mutation = {}

        # Start mutations after warm-up.
        if self.laps >= WARMUP_LAPS:

            self.generate_mutation()

        print("=" * 45)
        print()

    # ======================================
    # CAR CONTROLLER
    # ======================================

    def drive(self, s):

        speed = max(
            0.0,
            sensor(s, "speedX")
        )

        angle = sensor(
            s, "angle"
        )

        track_position = sensor(
            s, "trackPos"
        )

        lateral_speed = sensor(
            s, "speedY"
        )

        distance = sensor(
            s, "distFromStart"
        )

        beams = array(
            s, "track", 19, 200
        )

        target_position = (
            self.get_target_line(distance)
        )

        # ==================================
        # STEERING
        # ==================================

        steer = clamp(

            (
                angle * 10 / math.pi
            )

            - (
                track_position
                - target_position
            ) * 0.20

            - lateral_speed * 0.0025,

            -1,
            1

        )

        # ==================================
        # DYNAMIC SPEED CONTROL
        # ==================================

        # Find forward road visibility.
        clearance = max(

            max(0, beams[i])

            * math.cos(
                math.radians(ANGLES[i])
            )

            for i in range(7, 12)

        )

        clearance = max(
            0,
            clearance - 12
        )

        # Braking-distance estimate.
        # This is NOT a fixed speed cap.
        dynamic_speed = (

            3.6

            * math.sqrt(
                2 * 7.0 * clearance
            )

        )

        risk = (

            1

            + 0.85 * abs(steer)

            + 1.10 * abs(angle)

            + abs(lateral_speed) / 40

        )

        dynamic_speed /= max(
            risk,
            0.1
        )

        # Reduced speed for warm-up laps.
        if self.laps < WARMUP_LAPS:

            dynamic_speed *= 0.78

        # Edge protection.
        if abs(track_position) > 0.8:

            dynamic_speed *= 0.65

        # ==================================
        # ACCELERATION / BRAKING
        # ==================================

        accel = (

            1.0

            if speed < dynamic_speed - 5

            else 0.18

        )

        brake = clamp(

            (
                speed
                - dynamic_speed
            ) / 35,

            0,
            1

        )

        if brake > 0.15:
            accel = 0.0

        # ==================================
        # EXPERIMENTAL DRIFTING
        # ==================================

        # Simultaneous steering, throttle
        # and controlled brake input.
        #
        # Only active after warm-up.

        if (

            self.laps >= WARMUP_LAPS

            and 45 < speed

            and abs(lateral_speed) > 9

            and 0.12 < abs(steer) < 0.8

            and abs(track_position) < 0.55

            and clearance > 22

        ):

            accel = 0.42

            brake = max(
                brake,
                0.09
            )

        # ==================================
        # OPPONENT SAFETY
        # ==================================

        opponents = array(
            s, "opponents", 36
        )

        nearest_ahead = min(
            opponents[16:21]
        )

        if nearest_ahead < 12:

            accel = 0.0

            brake = max(

                brake,

                clamp(

                    (
                        12 - nearest_ahead
                    ) / 12,

                    0,
                    0.7

                )

            )

        # ==================================
        # RECOVERY
        # ==================================

        if (

            abs(track_position) > 1.25

            or abs(angle) > 1.4

        ):

            accel = min(
                accel,
                0.30
            )

            brake = 0.0

        # ==================================
        # AUTO GEARS
        # ==================================

        gear = int(
            sensor(s, "gear", 1)
        )

        rpm = sensor(
            s, "rpm"
        )

        if gear < 1:
            gear = 1

        if rpm > 7800 and gear < 6:
            gear += 1

        elif (

            rpm < 3000

            and speed > 12

            and gear > 1

        ):
            gear -= 1

        if speed < 8:
            gear = 1

        # ==================================
        # RETURN CONTROL ACTION
        # ==================================

        return {

            "steer": steer,

            "accel": accel,

            "brake": brake,

            "gear": gear

        }

#bro why is wispr flow so goated
#credits to wispr flow for helping me dictate this out