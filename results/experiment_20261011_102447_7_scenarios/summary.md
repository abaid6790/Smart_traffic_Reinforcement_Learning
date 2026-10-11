# Experiment results

Created 2026-10-11T10:24:47+05:00 by version 1.0.0. 20 runs per controller and scenario, base seed 42, 600 s of simulated traffic per run.

All controllers drove the **same traffic** in every run (same seed, scenario and duration). Numbers are means with 95 % confidence intervals (Student's t); "improvement" is the change of the mean relative to the baseline, and the verdict is "better"/"worse" only when the 95 % interval of the seed-by-seed difference excludes zero. See docs/EXPERIMENTS.md.

Q-Learning model: trained 700 episodes on low, medium, high, rush_hour, balanced, uneven, random (best policy from episode 20).

## Scenario: low

Tuned fixed-time green times: NS 10 s, EW 10 s (default: NS 30 s, EW 30 s); chosen on 4 separate tuning seeds.

| Metric | Fixed-time (default) | Fixed-time (tuned) | Q-Learning |
|---|---|---|---|
| Average waiting time (all vehicles) (s) | 9.7 ± 0.5 | 6.3 ± 0.3 | 11.4 ± 0.9 |
| Average waiting time (served vehicles) (s) | 10.1 ± 0.6 | 6.4 ± 0.3 | 11.5 ± 1.0 |
| Maximum waiting time (s) | 39.6 ± 0.4 | 20.6 ± 0.5 | 65.8 ± 2.4 |
| Average queue length (vehicles) | 1.5 ± 0.1 | 1.0 ± 0.1 | 1.7 ± 0.1 |
| Maximum queue length (vehicles) | 6.8 ± 0.6 | 5.0 ± 0.4 | 5.2 ± 0.2 |
| Vehicles served (vehicles) | 85.0 ± 3.8 | 85.3 ± 3.7 | 85.2 ± 3.8 |
| Throughput (vehicles/min) | 8.5 ± 0.4 | 8.5 ± 0.4 | 8.5 ± 0.4 |
| Average travel time (s) | 33.3 ± 0.8 | 30.1 ± 0.4 | 34.4 ± 1.0 |
| Average stops per vehicle (stops) | 0.60 ± 0.03 | 0.69 ± 0.03 | 0.52 ± 0.02 |
| Light switches (switches) | 16.0 ± 0.0 | 35.0 ± 0.0 | 11.5 ± 0.5 |
| Total reward (points) | -32.9 ± 0.4 | -70.8 ± 0.3 | -24.4 ± 1.1 |

**Q-Learning compared with Fixed-time (default)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | -17.1 % | worse (2/20 runs better) |
| Average waiting time (served vehicles) | -14.6 % | worse (4/20 runs better) |
| Maximum waiting time | -65.9 % | worse (0/20 runs better) |
| Average queue length | -16.1 % | worse (2/20 runs better) |
| Maximum queue length | +22.2 % | better (16/20 runs better) |
| Vehicles served | +0.3 % | no clear difference (10/20 runs better) |
| Throughput | +0.3 % | no clear difference (10/20 runs better) |
| Average travel time | -3.2 % | no clear difference (5/20 runs better) |
| Average stops per vehicle | +13.0 % | better (16/20 runs better) |
| Light switches | +28.1 % | better (20/20 runs better) |
| Total reward | n/a | better (20/20 runs better) |

**Q-Learning compared with Fixed-time (tuned)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | -81.4 % | worse (0/20 runs better) |
| Average waiting time (served vehicles) | -79.1 % | worse (0/20 runs better) |
| Maximum waiting time | -220.0 % | worse (0/20 runs better) |
| Average queue length | -79.7 % | worse (0/20 runs better) |
| Maximum queue length | -4.0 % | no clear difference (5/20 runs better) |
| Vehicles served | -0.1 % | no clear difference (5/20 runs better) |
| Throughput | -0.1 % | no clear difference (5/20 runs better) |
| Average travel time | -14.0 % | worse (0/20 runs better) |
| Average stops per vehicle | +25.2 % | better (20/20 runs better) |
| Light switches | +67.1 % | better (20/20 runs better) |
| Total reward | n/a | better (20/20 runs better) |

**Fixed-time (tuned) compared with Fixed-time (default)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | +35.4 % | better (20/20 runs better) |
| Average waiting time (served vehicles) | +36.0 % | better (20/20 runs better) |
| Maximum waiting time | +48.1 % | better (20/20 runs better) |
| Average queue length | +35.4 % | better (20/20 runs better) |
| Maximum queue length | +25.2 % | better (16/20 runs better) |
| Vehicles served | +0.4 % | no clear difference (8/20 runs better) |
| Throughput | +0.4 % | no clear difference (8/20 runs better) |
| Average travel time | +9.5 % | better (20/20 runs better) |
| Average stops per vehicle | -16.3 % | worse (1/20 runs better) |
| Light switches | -118.8 % | worse (0/20 runs better) |
| Total reward | n/a | worse (0/20 runs better) |

Checks: traffic identical for all controllers: yes; safety conflicts in all runs: 0.

## Scenario: medium

Tuned fixed-time green times: NS 10 s, EW 10 s (default: NS 30 s, EW 30 s); chosen on 4 separate tuning seeds.

| Metric | Fixed-time (default) | Fixed-time (tuned) | Q-Learning |
|---|---|---|---|
| Average waiting time (all vehicles) (s) | 10.5 ± 0.4 | 6.8 ± 0.3 | 7.3 ± 0.4 |
| Average waiting time (served vehicles) (s) | 10.8 ± 0.4 | 7.0 ± 0.3 | 7.5 ± 0.4 |
| Maximum waiting time (s) | 40.4 ± 0.5 | 21.7 ± 0.6 | 53.0 ± 4.5 |
| Average queue length (vehicles) | 3.2 ± 0.2 | 2.1 ± 0.1 | 2.2 ± 0.1 |
| Maximum queue length (vehicles) | 11.2 ± 0.7 | 8.9 ± 0.7 | 7.7 ± 0.6 |
| Vehicles served (vehicles) | 168.2 ± 7.2 | 170.8 ± 7.1 | 171.6 ± 7.2 |
| Throughput (vehicles/min) | 16.8 ± 0.7 | 17.1 ± 0.7 | 17.2 ± 0.7 |
| Average travel time (s) | 34.9 ± 0.6 | 31.4 ± 0.5 | 30.9 ± 0.4 |
| Average stops per vehicle (stops) | 0.72 ± 0.02 | 0.81 ± 0.02 | 0.66 ± 0.03 |
| Light switches (switches) | 16.0 ± 0.0 | 35.0 ± 0.0 | 21.9 ± 1.2 |
| Total reward (points) | -33.9 ± 0.7 | -71.9 ± 0.7 | -46.1 ± 2.1 |

**Q-Learning compared with Fixed-time (default)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | +30.4 % | better (20/20 runs better) |
| Average waiting time (served vehicles) | +30.7 % | better (20/20 runs better) |
| Maximum waiting time | -31.5 % | worse (2/20 runs better) |
| Average queue length | +30.7 % | better (20/20 runs better) |
| Maximum queue length | +31.6 % | better (20/20 runs better) |
| Vehicles served | +2.0 % | better (17/20 runs better) |
| Throughput | +2.0 % | better (17/20 runs better) |
| Average travel time | +11.4 % | better (20/20 runs better) |
| Average stops per vehicle | +7.1 % | better (17/20 runs better) |
| Light switches | -37.2 % | worse (0/20 runs better) |
| Total reward | n/a | worse (0/20 runs better) |

**Q-Learning compared with Fixed-time (tuned)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | -7.9 % | worse (6/20 runs better) |
| Average waiting time (served vehicles) | -7.5 % | worse (7/20 runs better) |
| Maximum waiting time | -144.5 % | worse (0/20 runs better) |
| Average queue length | -7.1 % | worse (6/20 runs better) |
| Maximum queue length | +13.5 % | better (14/20 runs better) |
| Vehicles served | +0.4 % | no clear difference (12/20 runs better) |
| Throughput | +0.4 % | no clear difference (12/20 runs better) |
| Average travel time | +1.5 % | no clear difference (14/20 runs better) |
| Average stops per vehicle | +18.4 % | better (20/20 runs better) |
| Light switches | +37.3 % | better (20/20 runs better) |
| Total reward | n/a | better (20/20 runs better) |

**Fixed-time (tuned) compared with Fixed-time (default)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | +35.5 % | better (20/20 runs better) |
| Average waiting time (served vehicles) | +35.5 % | better (20/20 runs better) |
| Maximum waiting time | +46.2 % | better (20/20 runs better) |
| Average queue length | +35.4 % | better (20/20 runs better) |
| Maximum queue length | +20.9 % | better (19/20 runs better) |
| Vehicles served | +1.5 % | better (17/20 runs better) |
| Throughput | +1.5 % | better (17/20 runs better) |
| Average travel time | +10.1 % | better (20/20 runs better) |
| Average stops per vehicle | -13.9 % | worse (0/20 runs better) |
| Light switches | -118.8 % | worse (0/20 runs better) |
| Total reward | n/a | worse (0/20 runs better) |

Checks: traffic identical for all controllers: yes; safety conflicts in all runs: 0.

## Scenario: high

Tuned fixed-time green times: NS 10 s, EW 10 s (default: NS 30 s, EW 30 s); chosen on 4 separate tuning seeds.

| Metric | Fixed-time (default) | Fixed-time (tuned) | Q-Learning |
|---|---|---|---|
| Average waiting time (all vehicles) (s) | 11.5 ± 0.3 | 7.8 ± 0.3 | 7.5 ± 0.3 |
| Average waiting time (served vehicles) (s) | 11.7 ± 0.3 | 7.9 ± 0.3 | 7.7 ± 0.3 |
| Maximum waiting time (s) | 42.4 ± 0.8 | 25.9 ± 1.7 | 44.5 ± 3.3 |
| Average queue length (vehicles) | 5.6 ± 0.2 | 3.8 ± 0.2 | 3.7 ± 0.2 |
| Maximum queue length (vehicles) | 18.2 ± 0.8 | 13.8 ± 1.1 | 12.5 ± 0.8 |
| Vehicles served (vehicles) | 270.6 ± 8.3 | 274.9 ± 7.9 | 276.8 ± 8.1 |
| Throughput (vehicles/min) | 27.1 ± 0.8 | 27.5 ± 0.8 | 27.7 ± 0.8 |
| Average travel time (s) | 37.2 ± 0.5 | 33.4 ± 0.5 | 32.2 ± 0.4 |
| Average stops per vehicle (stops) | 0.87 ± 0.03 | 0.97 ± 0.03 | 0.83 ± 0.02 |
| Light switches (switches) | 16.0 ± 0.0 | 35.0 ± 0.0 | 26.1 ± 0.9 |
| Total reward (points) | -35.9 ± 1.2 | -73.2 ± 0.8 | -57.4 ± 1.8 |

**Q-Learning compared with Fixed-time (default)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | +34.7 % | better (20/20 runs better) |
| Average waiting time (served vehicles) | +34.6 % | better (20/20 runs better) |
| Maximum waiting time | -5.1 % | no clear difference (9/20 runs better) |
| Average queue length | +34.5 % | better (20/20 runs better) |
| Maximum queue length | +31.5 % | better (19/20 runs better) |
| Vehicles served | +2.3 % | better (20/20 runs better) |
| Throughput | +2.3 % | better (20/20 runs better) |
| Average travel time | +13.6 % | better (20/20 runs better) |
| Average stops per vehicle | +4.3 % | better (15/20 runs better) |
| Light switches | -63.1 % | worse (0/20 runs better) |
| Total reward | n/a | worse (0/20 runs better) |

**Q-Learning compared with Fixed-time (tuned)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | +3.4 % | no clear difference (12/20 runs better) |
| Average waiting time (served vehicles) | +3.5 % | no clear difference (12/20 runs better) |
| Maximum waiting time | -71.8 % | worse (0/20 runs better) |
| Average queue length | +3.6 % | no clear difference (12/20 runs better) |
| Maximum queue length | +9.4 % | better (12/20 runs better) |
| Vehicles served | +0.7 % | better (16/20 runs better) |
| Throughput | +0.7 % | better (16/20 runs better) |
| Average travel time | +3.8 % | better (18/20 runs better) |
| Average stops per vehicle | +14.6 % | better (20/20 runs better) |
| Light switches | +25.4 % | better (20/20 runs better) |
| Total reward | n/a | better (20/20 runs better) |

**Fixed-time (tuned) compared with Fixed-time (default)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | +32.3 % | better (20/20 runs better) |
| Average waiting time (served vehicles) | +32.2 % | better (20/20 runs better) |
| Maximum waiting time | +38.8 % | better (20/20 runs better) |
| Average queue length | +32.1 % | better (20/20 runs better) |
| Maximum queue length | +24.4 % | better (19/20 runs better) |
| Vehicles served | +1.6 % | better (17/20 runs better) |
| Throughput | +1.6 % | better (17/20 runs better) |
| Average travel time | +10.2 % | better (20/20 runs better) |
| Average stops per vehicle | -12.0 % | worse (0/20 runs better) |
| Light switches | -118.8 % | worse (0/20 runs better) |
| Total reward | n/a | worse (0/20 runs better) |

Checks: traffic identical for all controllers: yes; safety conflicts in all runs: 0.

## Scenario: rush_hour

Tuned fixed-time green times: NS 20 s, EW 20 s (default: NS 30 s, EW 30 s); chosen on 4 separate tuning seeds.

| Metric | Fixed-time (default) | Fixed-time (tuned) | Q-Learning |
|---|---|---|---|
| Average waiting time (all vehicles) (s) | 13.6 ± 0.6 | 12.1 ± 0.6 | 11.6 ± 0.7 |
| Average waiting time (served vehicles) (s) | 13.8 ± 0.7 | 12.3 ± 0.7 | 11.9 ± 0.7 |
| Maximum waiting time (s) | 48.1 ± 2.0 | 42.1 ± 3.1 | 47.1 ± 4.4 |
| Average queue length (vehicles) | 10.2 ± 0.6 | 9.1 ± 0.6 | 8.8 ± 0.6 |
| Maximum queue length (vehicles) | 29.1 ± 1.9 | 25.4 ± 1.6 | 25.1 ± 2.2 |
| Vehicles served (vehicles) | 413.8 ± 9.2 | 416.6 ± 8.8 | 420.0 ± 8.2 |
| Throughput (vehicles/min) | 41.4 ± 0.9 | 41.7 ± 0.9 | 42.0 ± 0.8 |
| Average travel time (s) | 41.8 ± 1.1 | 40.2 ± 1.1 | 39.5 ± 1.1 |
| Average stops per vehicle (stops) | 1.10 ± 0.03 | 1.15 ± 0.04 | 1.18 ± 0.04 |
| Light switches (switches) | 16.0 ± 0.0 | 22.0 ± 0.0 | 26.8 ± 1.1 |
| Total reward (points) | -38.8 ± 1.3 | -50.4 ± 1.5 | -64.0 ± 3.4 |

**Q-Learning compared with Fixed-time (default)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | +14.6 % | better (20/20 runs better) |
| Average waiting time (served vehicles) | +13.6 % | better (19/20 runs better) |
| Maximum waiting time | +1.9 % | no clear difference (9/20 runs better) |
| Average queue length | +14.5 % | better (20/20 runs better) |
| Maximum queue length | +13.9 % | better (16/20 runs better) |
| Vehicles served | +1.5 % | better (18/20 runs better) |
| Throughput | +1.5 % | better (18/20 runs better) |
| Average travel time | +5.4 % | better (18/20 runs better) |
| Average stops per vehicle | -8.2 % | worse (1/20 runs better) |
| Light switches | -67.2 % | worse (0/20 runs better) |
| Total reward | n/a | worse (0/20 runs better) |

**Q-Learning compared with Fixed-time (tuned)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | +3.8 % | better (15/20 runs better) |
| Average waiting time (served vehicles) | +2.9 % | no clear difference (14/20 runs better) |
| Maximum waiting time | -11.9 % | worse (7/20 runs better) |
| Average queue length | +3.8 % | better (15/20 runs better) |
| Maximum queue length | +1.6 % | no clear difference (12/20 runs better) |
| Vehicles served | +0.8 % | better (18/20 runs better) |
| Throughput | +0.8 % | better (18/20 runs better) |
| Average travel time | +1.8 % | better (16/20 runs better) |
| Average stops per vehicle | -2.6 % | no clear difference (6/20 runs better) |
| Light switches | -21.6 % | worse (1/20 runs better) |
| Total reward | n/a | worse (1/20 runs better) |

**Fixed-time (tuned) compared with Fixed-time (default)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | +11.3 % | better (19/20 runs better) |
| Average waiting time (served vehicles) | +11.1 % | better (19/20 runs better) |
| Maximum waiting time | +12.4 % | better (17/20 runs better) |
| Average queue length | +11.2 % | better (19/20 runs better) |
| Maximum queue length | +12.5 % | better (17/20 runs better) |
| Vehicles served | +0.7 % | better (16/20 runs better) |
| Throughput | +0.7 % | better (16/20 runs better) |
| Average travel time | +3.7 % | better (18/20 runs better) |
| Average stops per vehicle | -5.4 % | worse (1/20 runs better) |
| Light switches | -37.5 % | worse (0/20 runs better) |
| Total reward | n/a | worse (0/20 runs better) |

Checks: traffic identical for all controllers: yes; safety conflicts in all runs: 0.

## Scenario: balanced

Tuned fixed-time green times: NS 10 s, EW 10 s (default: NS 30 s, EW 30 s); chosen on 4 separate tuning seeds.

| Metric | Fixed-time (default) | Fixed-time (tuned) | Q-Learning |
|---|---|---|---|
| Average waiting time (all vehicles) (s) | 11.0 ± 0.4 | 7.0 ± 0.3 | 7.0 ± 0.2 |
| Average waiting time (served vehicles) (s) | 11.2 ± 0.4 | 7.1 ± 0.3 | 7.1 ± 0.3 |
| Maximum waiting time (s) | 41.1 ± 0.5 | 23.5 ± 0.8 | 48.1 ± 5.0 |
| Average queue length (vehicles) | 4.2 ± 0.2 | 2.6 ± 0.2 | 2.7 ± 0.2 |
| Maximum queue length (vehicles) | 14.0 ± 1.1 | 10.4 ± 1.0 | 9.6 ± 0.8 |
| Vehicles served (vehicles) | 209.8 ± 8.4 | 213.2 ± 8.1 | 214.8 ± 8.4 |
| Throughput (vehicles/min) | 21.0 ± 0.8 | 21.3 ± 0.8 | 21.5 ± 0.8 |
| Average travel time (s) | 35.9 ± 0.6 | 31.9 ± 0.4 | 31.0 ± 0.4 |
| Average stops per vehicle (stops) | 0.78 ± 0.02 | 0.88 ± 0.03 | 0.74 ± 0.02 |
| Light switches (switches) | 16.0 ± 0.0 | 35.0 ± 0.0 | 24.9 ± 0.8 |
| Total reward (points) | -34.6 ± 0.7 | -72.0 ± 0.9 | -53.4 ± 1.7 |

**Q-Learning compared with Fixed-time (default)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | +36.6 % | better (20/20 runs better) |
| Average waiting time (served vehicles) | +37.2 % | better (20/20 runs better) |
| Maximum waiting time | -16.9 % | worse (7/20 runs better) |
| Average queue length | +36.5 % | better (20/20 runs better) |
| Maximum queue length | +31.4 % | better (19/20 runs better) |
| Vehicles served | +2.4 % | better (20/20 runs better) |
| Throughput | +2.4 % | better (20/20 runs better) |
| Average travel time | +13.8 % | better (20/20 runs better) |
| Average stops per vehicle | +5.5 % | better (17/20 runs better) |
| Light switches | -55.3 % | worse (0/20 runs better) |
| Total reward | n/a | worse (0/20 runs better) |

**Q-Learning compared with Fixed-time (tuned)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | -0.5 % | no clear difference (10/20 runs better) |
| Average waiting time (served vehicles) | +0.7 % | no clear difference (12/20 runs better) |
| Maximum waiting time | -104.7 % | worse (0/20 runs better) |
| Average queue length | -0.4 % | no clear difference (10/20 runs better) |
| Maximum queue length | +7.7 % | no clear difference (8/20 runs better) |
| Vehicles served | +0.7 % | better (13/20 runs better) |
| Throughput | +0.7 % | better (13/20 runs better) |
| Average travel time | +3.0 % | better (17/20 runs better) |
| Average stops per vehicle | +15.8 % | better (20/20 runs better) |
| Light switches | +29.0 % | better (20/20 runs better) |
| Total reward | n/a | better (20/20 runs better) |

**Fixed-time (tuned) compared with Fixed-time (default)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | +36.9 % | better (20/20 runs better) |
| Average waiting time (served vehicles) | +36.8 % | better (20/20 runs better) |
| Maximum waiting time | +42.9 % | better (20/20 runs better) |
| Average queue length | +36.7 % | better (20/20 runs better) |
| Maximum queue length | +25.7 % | better (19/20 runs better) |
| Vehicles served | +1.6 % | better (16/20 runs better) |
| Throughput | +1.6 % | better (16/20 runs better) |
| Average travel time | +11.2 % | better (20/20 runs better) |
| Average stops per vehicle | -12.2 % | worse (1/20 runs better) |
| Light switches | -118.8 % | worse (0/20 runs better) |
| Total reward | n/a | worse (0/20 runs better) |

Checks: traffic identical for all controllers: yes; safety conflicts in all runs: 0.

## Scenario: uneven

Tuned fixed-time green times: NS 20 s, EW 10 s (default: NS 30 s, EW 30 s); chosen on 4 separate tuning seeds.

| Metric | Fixed-time (default) | Fixed-time (tuned) | Q-Learning |
|---|---|---|---|
| Average waiting time (all vehicles) (s) | 12.1 ± 0.5 | 7.6 ± 0.3 | 7.6 ± 0.3 |
| Average waiting time (served vehicles) (s) | 12.2 ± 0.6 | 7.7 ± 0.3 | 7.7 ± 0.4 |
| Maximum waiting time (s) | 44.3 ± 1.7 | 31.2 ± 1.2 | 62.8 ± 3.1 |
| Average queue length (vehicles) | 4.6 ± 0.3 | 2.9 ± 0.2 | 2.9 ± 0.2 |
| Maximum queue length (vehicles) | 17.6 ± 1.2 | 11.2 ± 0.7 | 10.5 ± 0.9 |
| Vehicles served (vehicles) | 208.3 ± 6.8 | 216.9 ± 6.8 | 216.2 ± 6.8 |
| Throughput (vehicles/min) | 20.8 ± 0.7 | 21.7 ± 0.7 | 21.6 ± 0.7 |
| Average travel time (s) | 38.1 ± 0.9 | 32.6 ± 0.5 | 31.3 ± 0.4 |
| Average stops per vehicle (stops) | 0.89 ± 0.03 | 0.89 ± 0.03 | 0.75 ± 0.03 |
| Light switches (switches) | 16.0 ± 0.0 | 27.0 ± 0.0 | 19.3 ± 1.0 |
| Total reward (points) | -33.6 ± 0.7 | -55.4 ± 0.5 | -41.6 ± 1.9 |

**Q-Learning compared with Fixed-time (default)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | +37.2 % | better (20/20 runs better) |
| Average waiting time (served vehicles) | +37.0 % | better (20/20 runs better) |
| Maximum waiting time | -41.6 % | worse (0/20 runs better) |
| Average queue length | +37.2 % | better (20/20 runs better) |
| Maximum queue length | +40.3 % | better (19/20 runs better) |
| Vehicles served | +3.8 % | better (20/20 runs better) |
| Throughput | +3.8 % | better (20/20 runs better) |
| Average travel time | +17.9 % | better (20/20 runs better) |
| Average stops per vehicle | +15.6 % | better (20/20 runs better) |
| Light switches | -20.6 % | worse (1/20 runs better) |
| Total reward | n/a | worse (1/20 runs better) |

**Q-Learning compared with Fixed-time (tuned)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | -0.6 % | no clear difference (9/20 runs better) |
| Average waiting time (served vehicles) | -0.3 % | no clear difference (9/20 runs better) |
| Maximum waiting time | -101.4 % | worse (0/20 runs better) |
| Average queue length | -0.4 % | no clear difference (9/20 runs better) |
| Maximum queue length | +6.2 % | no clear difference (10/20 runs better) |
| Vehicles served | -0.4 % | no clear difference (5/20 runs better) |
| Throughput | -0.4 % | no clear difference (5/20 runs better) |
| Average travel time | +4.0 % | better (16/20 runs better) |
| Average stops per vehicle | +15.5 % | better (20/20 runs better) |
| Light switches | +28.5 % | better (20/20 runs better) |
| Total reward | n/a | better (20/20 runs better) |

**Fixed-time (tuned) compared with Fixed-time (default)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | +37.6 % | better (20/20 runs better) |
| Average waiting time (served vehicles) | +37.2 % | better (20/20 runs better) |
| Maximum waiting time | +29.7 % | better (20/20 runs better) |
| Average queue length | +37.5 % | better (20/20 runs better) |
| Maximum queue length | +36.4 % | better (20/20 runs better) |
| Vehicles served | +4.2 % | better (19/20 runs better) |
| Throughput | +4.2 % | better (19/20 runs better) |
| Average travel time | +14.5 % | better (20/20 runs better) |
| Average stops per vehicle | +0.1 % | no clear difference (11/20 runs better) |
| Light switches | -68.8 % | worse (0/20 runs better) |
| Total reward | n/a | worse (0/20 runs better) |

Checks: traffic identical for all controllers: yes; safety conflicts in all runs: 0.

## Scenario: random

Tuned fixed-time green times: NS 10 s, EW 10 s (default: NS 30 s, EW 30 s); chosen on 4 separate tuning seeds.

| Metric | Fixed-time (default) | Fixed-time (tuned) | Q-Learning |
|---|---|---|---|
| Average waiting time (all vehicles) (s) | 11.5 ± 0.4 | 7.7 ± 0.3 | 7.9 ± 0.3 |
| Average waiting time (served vehicles) (s) | 11.7 ± 0.4 | 8.0 ± 0.4 | 8.0 ± 0.4 |
| Maximum waiting time (s) | 42.5 ± 1.0 | 27.4 ± 1.7 | 53.5 ± 5.1 |
| Average queue length (vehicles) | 4.3 ± 0.2 | 2.9 ± 0.2 | 2.9 ± 0.1 |
| Maximum queue length (vehicles) | 15.8 ± 1.2 | 12.2 ± 1.2 | 11.8 ± 0.9 |
| Vehicles served (vehicles) | 206.7 ± 5.8 | 210.2 ± 5.1 | 210.9 ± 5.2 |
| Throughput (vehicles/min) | 20.7 ± 0.6 | 21.0 ± 0.5 | 21.1 ± 0.5 |
| Average travel time (s) | 36.8 ± 0.5 | 33.3 ± 0.5 | 32.2 ± 0.4 |
| Average stops per vehicle (stops) | 0.85 ± 0.02 | 0.98 ± 0.03 | 0.81 ± 0.03 |
| Light switches (switches) | 16.0 ± 0.0 | 35.0 ± 0.0 | 22.3 ± 1.3 |
| Total reward (points) | -34.6 ± 1.0 | -72.5 ± 1.2 | -48.1 ± 2.8 |

**Q-Learning compared with Fixed-time (default)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | +31.6 % | better (20/20 runs better) |
| Average waiting time (served vehicles) | +31.6 % | better (20/20 runs better) |
| Maximum waiting time | -25.8 % | worse (5/20 runs better) |
| Average queue length | +31.5 % | better (20/20 runs better) |
| Maximum queue length | +25.2 % | better (19/20 runs better) |
| Vehicles served | +2.1 % | better (15/20 runs better) |
| Throughput | +2.1 % | better (15/20 runs better) |
| Average travel time | +12.4 % | better (20/20 runs better) |
| Average stops per vehicle | +5.3 % | better (16/20 runs better) |
| Light switches | -39.4 % | worse (0/20 runs better) |
| Total reward | n/a | worse (0/20 runs better) |

**Q-Learning compared with Fixed-time (tuned)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | -1.6 % | no clear difference (8/20 runs better) |
| Average waiting time (served vehicles) | -0.6 % | no clear difference (8/20 runs better) |
| Maximum waiting time | -95.2 % | worse (0/20 runs better) |
| Average queue length | -1.3 % | no clear difference (8/20 runs better) |
| Maximum queue length | +2.5 % | no clear difference (9/20 runs better) |
| Vehicles served | +0.4 % | no clear difference (13/20 runs better) |
| Throughput | +0.4 % | no clear difference (13/20 runs better) |
| Average travel time | +3.4 % | better (17/20 runs better) |
| Average stops per vehicle | +17.5 % | better (20/20 runs better) |
| Light switches | +36.3 % | better (20/20 runs better) |
| Total reward | n/a | better (20/20 runs better) |

**Fixed-time (tuned) compared with Fixed-time (default)** (positive improvement = better)

| Metric | Improvement | Verdict |
|---|---|---|
| Average waiting time (all vehicles) | +32.6 % | better (20/20 runs better) |
| Average waiting time (served vehicles) | +32.0 % | better (20/20 runs better) |
| Maximum waiting time | +35.5 % | better (20/20 runs better) |
| Average queue length | +32.4 % | better (20/20 runs better) |
| Maximum queue length | +23.3 % | better (19/20 runs better) |
| Vehicles served | +1.7 % | better (17/20 runs better) |
| Throughput | +1.7 % | better (17/20 runs better) |
| Average travel time | +9.4 % | better (20/20 runs better) |
| Average stops per vehicle | -14.8 % | worse (0/20 runs better) |
| Light switches | -118.8 % | worse (0/20 runs better) |
| Total reward | n/a | worse (0/20 runs better) |

Checks: traffic identical for all controllers: yes; safety conflicts in all runs: 0.

## Honest notes

* The Q-Learning agent can only be as good as its training; a model trained on other scenarios than the one tested is being tested on traffic it has not seen.
* *Total reward* is the training reward formula applied identically to every controller on a 5 s grid. It penalises light switches, so it can rank controllers differently from waiting time; waiting time and queue length are the measures to judge by.
* The tuned fixed-time controller's green times were chosen on separate seeds, not on the seeds shown here.
