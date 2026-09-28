# Step-Indexed vs Encoder-Indexed Triggering

## Step-indexed triggering

The firmware triggers the camera when commanded step count reaches the next trigger position.

Pros:

- possible immediately;
- simple implementation;
- aligns trigger schedule with motion planner.

Cons:

- commanded position is not measured position;
- missed steps, backlash, elasticity and screw/belt errors are invisible.

## Encoder-indexed triggering

The firmware triggers the camera when measured encoder count reaches the next trigger position.

Pros:

- frame coordinate is based on measured position;
- motion errors become observable;
- better path to low-overlap coordinate tiling.

Cons:

- requires robust encoder inputs;
- requires direction handling, filtering and error flags;
- schedule must handle jitter/noise and stalls.

## Hybrid mode

Hybrid mode is mandatory as transition:

```text
trigger source = steps
metadata = steps + encoder counts
```

It allows measurement before switching control.
