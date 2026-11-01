#this should detect the torcs race config and the ummm yah seperate or pre(or just trained)model

import argparse
import xml.etree.ElementTree as ET
from pathlib import path
from brain import EvoBrain #the main brain😎


def detect_track(torcs_dir, mode):
    if torcs_dir:
        base = Path(torcs_dir).expanduser()
        candidates = [
            base / "config" / "raceman" / f"{mode}.xml",
            base / "torcs" / "config" / "raceman" / f"{mode}.xml"
        ]
    else:
        candidates = [
            Path.cwd() / "config" / "raceman" / f"{mode}.xml",
            Path.home() / ".torcs" / "config" / "raceman" / f"{mode}.xml"
        ]

    for path in candidates:
        if not path.is_file():
            continue
        try:
            root = ET.parse(path).getroot()
            for section in root.iter("section"):
                if section.get("name") != "Tracks":
                    continue
                for child in section.findall("section"):
                    attrs = {
                        node.get("name"): node.get("val")
                        for node in child.findall("attstr")
                    }
                    if attrs.get("name"):
                        return (
                            f"{attrs.get('category', 'road')}_"
                            f"{attrs['name']}"
                        )
        except ET.ParseError:
            continue
    return None

def run(args):
    print("SCR Evolution has Started👍✌️")
    print("Ctrl + C to kill mini max(maybe)")

    if args.track == "auto":
        track = detect_track(args.torchs_dir, args.race_mode)
        if not track:
            raise SystemExit(
                "Could not detect track. Supply --torcs-dir "
                "or --track NAME. SCR telemetry does not "
                "include a reliable track name."
            )
        else:
            tracks = args.track

        print(
            f"Track profile: {track} | "
            "warmup: 3 completed laps | fixed speed cap: none"
        )

        client = SCRClient(args.host, args.port, args.driver_id)
    brain = EvoBrain(track)

    try:
        client.connect()
        ticks = 0
        missing = 0

        while True:
            state, status = client.read()

            if status == "finished":
                print(
                    "Race finished/restarted. Reconnecting "
                    "without changing SCR server."
                )
                track = (
                    detect_track(args.torcs_dir, args.race_mode)
                    if args.track == "auto"
                    else args.track
                ) or track
                brain = EvoBrain(track)
                client.connect()
                continue

            if status == "timeout":
                missing += 1
                if missing >= 10:
                    print("No telemetry for 10 seconds. Reconnecting...")
                    client.close()
                    client = SCRClient(
                        args.host, args.port, args.driver_id
                    )
                    track = (
                        detect_track(args.torcs_dir, args.race_mode)
                        if args.track == "auto"
                        else args.track
                    ) or track
                    brain = EvoBrain(track)
                    client.connect()
                    missing = 0
                continue

            missing = 0
            brain.observe(state)
            action = brain.drive(state)
            client.send(action)

            ticks += 1
            if ticks % 250 == 0:
                print(
                    f"{track} | lap {brain.laps + 1} | "
                    f"{sensor(state, 'speedX'):.0f} km/h | "
                    f"pos {sensor(state, 'trackPos'):.2f} | "
                    f"steer {action['steer']:.2f} | "
                    f"best {brain.best_time:.1f}s"
                )

    except KeyboardInterrupt:
        print("Stopped. Saved models remain in models/")
    finally:
        client.close()

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=3001)
    p.add_argument("--driver-id", default="SCR")
    p.add_argument("--torcs-dir", default="")
    p.add_argument(
        "--race-mode",
        choices=["quickrace", "practice"],
        default="quickrace"
    )
    p.add_argument(
        "--track",
        default="auto",
        help="auto or a unique track name"
    )
    run(p.parse_args())
    #will it work?
