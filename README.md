
# SCR Evolution Racing

Experimental self-improving Python racing driver for TORCS SCR. (still not rl just a rule based mutating ai)

## Start

1. Open TORCS.
2. Open Race > Quick Race > Configure Race.
3. Select a track.
4. Select `scr_server 1`.
5. Configure at least 10 laps.
6. Start the Python client.
7. Select New Race in TORCS.

## RUN

- will add the commands soon
- plz wait coz i gotta personally test it 
## Features

- SCR UDP protocol
- Universal track-sensor-based controller
- Automatic gears
- No fixed maximum speed
- Dynamic braking
- Three warm-up laps per session
- Evolutionary racing-line tuning
- Per-track model persistence
- Approximate opponent-line observations
- Experimental steering/throttle/brake drifting

## Learning

The AI records sector positions during laps.

After each clean lap, it compares the lap time with its
best recorded lap.

The faster clean lap becomes the new best model.

Following the warm-up phase, it generates random
per-sector mutations and tests them on future laps.

Trained models are saved in the models directory.

## Limitations

This is an experimental evolutionary controller, not
a trained neural network or a complete RL implementation.

A best lap must be completed before the model can learn.

Drifting is experimental and not guaranteed.

Exact opponent racing lines are not available through
ordinary SCR telemetry.

Performance has not been validated on every TORCS track.

## Testing

```powershell
py -m py_compile main.py scr.py brain.py test_smoke.py
py test_smoke.py
```

## License

Original educational AI client code.

TORCS is a separate project.
TORCS game files and assets are not included.
