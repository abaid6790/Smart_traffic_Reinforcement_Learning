# Performance Metrics

How every number in the results is calculated. The code is in
`evaluation/metrics.py`; the tests in `tests/test_metrics.py` check each formula against
values worked out by hand.

## Words used

| Word | Meaning |
|------|---------|
| arrived | every vehicle that has appeared during the run |
| served (completed) | arrived vehicles that have driven all the way out of the map |
| unserved | arrived vehicles still on the road, or waiting outside a full road, when the run ends |
| waiting | a vehicle is moving slower than 0.5 m/s **before the stop line** (this includes waiting to enter a full road). Time spent crawling or stopped after the stop line is not waiting time |
| stop | one separate time a vehicle comes to a halt (see below) |
| queue | vehicles that are waiting, as defined above, on one road |

## The metrics

| Metric | Formula | Unit |
|--------|---------|------|
| `vehicles_arrived` | count of arrived vehicles | vehicles |
| `vehicles_served` | count of served vehicles | vehicles |
| `vehicles_unserved` | arrived − served | vehicles |
| `average_waiting_time` | sum of waiting time of served vehicles ÷ number of served vehicles | s |
| `average_waiting_time_all` | sum of waiting time of **all arrived** vehicles ÷ number arrived | s |
| `max_waiting_time` | largest waiting time of any arrived vehicle | s |
| `average_queue_length` | the total queue (all four roads added together) measured after every simulation step, averaged over all steps | vehicles |
| `average_queue_by_road` | the same, separately for each road (the four values add up to the average above) | vehicles |
| `max_queue_length` | the largest total queue seen after any step | vehicles |
| `average_travel_time` | mean of (time of leaving − time of arrival) for served vehicles | s |
| `average_stops` | mean number of stops per served vehicle | stops |
| `total_stops` | number of stops of all arrived vehicles | stops |
| `throughput_per_minute` | served vehicles ÷ simulated minutes | vehicles/min |
| `light_switches` | number of times the light started a phase change | count |
| `safety_violations` | simulation steps in which vehicles from both road pairs were in the crossing at once (must be 0) | steps |

### Why there are two average waiting times

`average_waiting_time` is the standard definition, but it only looks at vehicles that
finished. A controller that leaves many cars stuck in queues when the run ends could
look better than it really is. `average_waiting_time_all` counts those vehicles too
(with the waiting time they have built up so far), and `vehicles_unserved` shows how
many there were. When comparing controllers, check all three. If they tell different
stories, say so in the report.

### What counts as a stop

A vehicle stops when its speed falls below 0.5 m/s. It can only stop *again* after it
has got back up to at least 1.0 m/s. A queue creeping forward in small shuffles is
therefore counted as one stop, not dozens. A vehicle that waits outside a full road
counts one stop.

### When a value cannot be computed

If an average has nothing to average (for example, no vehicle was served), the value is
`None` (shown as `n/a`), never `0`. Zero would look like perfect performance.

## Time series (for graphs)

`TimeSeries` holds values sampled every 5 simulated seconds (configurable):

* `total_queue`: total queue at that moment
* `vehicles_in_system`: arrived but not yet left (including those waiting outside)
* `average_wait_so_far`: average waiting time of the vehicles served up to that moment
  (`None` until the first one is served)

## Percent improvement

Used to compare a candidate (the RL agent) with the baseline (the fixed-time controller):

* when **lower is better** (waiting time, queue length, travel time, stops):

  `improvement = (baseline − candidate) ÷ baseline × 100`

* when **higher is better** (vehicles served, throughput):

  `improvement = (candidate − baseline) ÷ baseline × 100`

A positive number means the candidate did better and a negative number means it did
worse. If the baseline is 0 (and the values differ) or either value is missing, the
result is `None`. Two equal values give 0.

Example: waiting time 42.7 s → 28.4 s gives (42.7 − 28.4) ÷ 42.7 × 100 = 33.5 %.

## Things to keep in mind when reading results

* **One run is not enough.** With the fixed controller in rush hour, the average
  waiting time over 20 different seeds had a mean of 13.8 s and a standard deviation of
  0.9 s (about 7 %). Differences smaller than that between single runs mean nothing.
  The experiment system (`--experiment`, see `docs/EXPERIMENTS.md`) repeats each
  comparison over many seeds and gives every controller the same traffic for each seed.
* **Runs have an end.** Vehicles that arrive near the end cannot finish, and the queue
  at the start of a run is empty. Both controllers are affected the same way because
  they see identical traffic, but absolute numbers depend on the run length.
* **Throughput counts vehicles that have left the map** (about 5 s after crossing the
  stop line), not vehicles that crossed the stop line.
* **This is a simulation.** The numbers describe this simplified model, not real roads.

## Statistics used by the experiments (Phase 7)

* **Mean, standard deviation, 95 % confidence interval:** `mean ± t × std / sqrt(n)` with the sample
  standard deviation (n − 1) and the Student-t value for n − 1 degrees of freedom.
* **Paired comparison:** for each seed the candidate's value minus the baseline's value; the verdict is
  "better"/"worse" only if the 95 % interval of those differences excludes 0, otherwise "no clear difference".
  The columns "runs better" count seeds where the candidate won.
* **Total reward:** the RL reward summed over a run, computed for *every* controller on the same 5 s grid, so it is
  comparable. It includes the switch penalty, so it does not rank controllers the same way waiting time does.
  Its improvement percentage is shown as `n/a` (a sum of mostly negative numbers has no meaningful percentage).
