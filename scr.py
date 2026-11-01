
"""Minimal TORCS SCR UDP client. Standard library only."""
import re
import socket
import time

ANGLES = [-90, -75, -60, -45, -30, -20, -15, -10, -5,
          0, 5, 10, 15, 20, 30, 45, 60, 75, 90]
FIELDS = re.compile(r"\(([A-Za-z][A-Za-z0-9]*)\s+([^()]*)\)")


def clamp(x, a, b):
    return max(a, min(b, x))


def parse_packet(message):
    result = {}
    for key, content in FIELDS.findall(message):
        try:
            values = [float(x) for x in content.split()]
        except ValueError:
            continue
        if values:
            result[key] = values if len(values) != 1 else values[0]
    return result


def sensor(state, key, default=0.0):
    value = state.get(key, default)
    return value if isinstance(value, (int, float)) else default


def array(state, key, count, default=200.0):
    value = state.get(key)
    if isinstance(value, list) and len(value) == count:
        return value
    return [default] * count


def control_packet(action):
    gear = int(clamp(action.get("gear", 1), -1, 6))
    return (
        f"(accel {clamp(action.get('accel', 0), 0, 1):.4f})"
        f"(brake {clamp(action.get('brake', 0), 0, 1):.4f})"
        f"(steer {clamp(action.get('steer', 0), -1, 1):.4f})"
        f"(gear {gear})(clutch 0)(meta 0)"
    ).encode("ascii")


class SCRClient:
    def __init__(self, host="127.0.0.1", port=3001, driver_id="SCR"):
        self.address = (socket.gethostbyname(host), port)
        self.driver_id = driver_id
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(1.0)

    def connect(self):
        init = f"{self.driver_id}(init {' '.join(map(str, ANGLES))})".encode()
        print(f"Waiting for TORCS SCR at {self.address[0]}:{self.address[1]} ...")
        while True:
            self.sock.sendto(init, self.address)
            try:
                data, address = self.sock.recvfrom(65535)
            except socket.timeout:
                continue
            if address[0] != self.address[0]:
                continue
            if b"***identified***" in data:
                print("SCR connected. Race starting!")
                return
            time.sleep(0.05)

    def read(self):
        while True:
            try:
                data, addr = self.sock.recvfrom(65535)
            except socket.timeout:
                return None, "timeout"
            if addr[0] != self.address[0]:
                continue
            message = data.decode("ascii", errors="ignore")
            if "***shutdown***" in message or "***restart***" in message:
                return None, "finished"
            if "***identified***" in message:
                continue
            state = parse_packet(message)
            if "speedX" in state and "trackPos" in state:
                return state, "data"

    def send(self, action):
        self.sock.sendto(control_packet(action), self.address)

    def close(self):
        self.sock.close()
