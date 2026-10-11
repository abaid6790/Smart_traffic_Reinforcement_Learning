# Disclaimer and responsible use

## Educational use only

This project is an **academic simulation**. It was built to study reinforcement learning, not to control traffic.

* **Do not connect it to real traffic-control equipment**, signals, sensors or vehicles, and do not use its output to make
  decisions about real roads. A real controller needs safety engineering, standards compliance, fail-safe hardware,
  certification and testing that this project does not have.
* The simulation is simplified: one intersection, straight traffic, a simple driver model and random arrivals at fixed
  average rates. Its results say nothing certain about real traffic.
* The trained agent is a small table of 36 numbers learned in simulation. It was not better than a well-tuned fixed timer in
  most scenarios ([PROJECT_REPORT.md](PROJECT_REPORT.md)).

## No warranty

The software is provided "as is", without warranty of any kind, as stated in the [MIT licence](../LICENSE). The authors are
not liable for any damage or loss arising from its use.

## Results

All numbers in the documentation come from real runs of this program with the settings and seeds stated. They apply to
those settings only. Another model, other seeds or other settings give other numbers. Do not quote the results without the
conditions (scenario, 20 runs, 600 s, base seed 42, one model trained for 700 episodes).

## Academic integrity

If you submit this project, say clearly what is your own work and what is not, follow your institution's rules on
collaboration and on the use of tools, and credit the sources in [PROJECT_REPORT.md](PROJECT_REPORT.md) and
[THIRD_PARTY_NOTICES.md](../THIRD_PARTY_NOTICES.md). Be able to explain every part of it
([VIVA_QUESTIONS.md](VIVA_QUESTIONS.md)).

## Privacy and security

See [PRIVACY.md](../PRIVACY.md), [COOKIE_POLICY.md](../COOKIE_POLICY.md) and [SECURITY.md](../SECURITY.md).
