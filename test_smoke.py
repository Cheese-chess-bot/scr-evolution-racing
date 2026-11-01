from tempfile import TemporaryDirectory
from pathlib import Path
from main import detect_track
from brain import EvoBrain
from scr import parse_packet, control_packet


def test_protocol():
    s = parse_packet(
        '(angle 0.12)(trackPos -0.4)'
        '(speedX 123.5)(track 1 2 3)'
    )
    assert s['speedX'] == 123.5
    assert s['track'] == [1, 2, 3]

    command = control_packet({
        'accel': 2,
        'brake': -1,
        'steer': 0.15,
        'gear': 3
    })
    assert b'(accel 1.0000)' in command
    assert b'(brake 0.0000)' in command


def test_learning():
    with TemporaryDirectory() as dirname:
        b = EvoBrain('road_test', dirname)
        for k in range(22):
            b.samples[str(k)] = {
                'sum_pos': 0.1,
                'sum_speed': 130.,
                'n': 1
            }
        b.bad_ticks, b.total_ticks = 0, 500
        b.start_damage = 0
        b.finish_lap(80.0, 0)

        assert b.best_time == 80
        assert b.path.exists()

        b2 = EvoBrain('road_test', dirname)
        assert b2.best_line['10'] == 0.1


def test_track_xml():
    with TemporaryDirectory() as dirname:
        path = (
            Path(dirname) / 'config'
            / 'raceman' / 'quickrace.xml'
        )
        path.parent.mkdir(parents=True)
        path.write_text(
            '<params><section name="Tracks">'
            '<section name="1">'
            '<attstr name="name" val="alpine-1"/>'
            '<attstr name="category" val="road"/>'
            '</section></section></params>'
        )
        assert detect_track(
            dirname, 'quickrace'
        ) == 'road_alpine-1'


if __name__ == '__main__':
    test_protocol()
    test_learning()
    test_track_xml()
    print(
        'PASS: SCR protocol, brain save/load, '
        'TORCS track detection'
    )
