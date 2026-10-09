import math
import unittest

from config.settings import SimulationConfig
from environment.enums import Direction
from environment.vehicle import Vehicle

CFG = SimulationConfig()
DT = CFG.dt
STOP_LINE = CFG.road_length
END = STOP_LINE + CFG.intersection_length + CFG.exit_length


def make_vehicle(**kwargs):
    defaults = dict(id=1, direction=Direction.NORTH, max_speed=CFG.max_speed_ms,
                    length=CFG.vehicle_length, position=CFG.vehicle_length)
    defaults.update(kwargs)
    return Vehicle(**defaults)


def drive(vehicle, limit=math.inf):
    vehicle.drive(DT, limit, CFG.acceleration, CFG.braking, CFG.halting_speed, STOP_LINE, END)


class CreationTests(unittest.TestCase):
    def test_new_vehicle_defaults(self):
        v = Vehicle(id=7, direction=Direction.EAST, max_speed=12.0, length=4.5)
        self.assertEqual((v.id, v.direction, v.max_speed), (7, Direction.EAST, 12.0))
        self.assertEqual((v.speed, v.waiting_time, v.travel_time, v.stops), (0.0, 0.0, 0.0, 0))
        self.assertFalse(v.stopped or v.completed or v.entered)

    def test_rear_is_behind_the_front_bumper(self):
        v = make_vehicle(position=20.0, length=4.5)
        self.assertEqual(v.rear, 15.5)


class MovementTests(unittest.TestCase):
    def test_accelerates_gradually_and_never_exceeds_max_speed(self):
        v = make_vehicle()
        speeds = []
        for _ in range(40):
            drive(v)
            speeds.append(v.speed)
        self.assertAlmostEqual(speeds[0], CFG.acceleration * DT)
        self.assertTrue(all(b >= a for a, b in zip(speeds, speeds[1:])))
        self.assertAlmostEqual(max(speeds), v.max_speed)

    def test_moves_forward_by_speed_times_dt(self):
        v = make_vehicle(speed=10.0)
        before = v.position
        drive(v)
        self.assertAlmostEqual(v.position - before, v.speed * DT)

    def test_never_moves_past_its_limit(self):
        v = make_vehicle(speed=v_max())
        limit = 60.0
        for _ in range(200):
            drive(v, limit)
            self.assertLessEqual(v.position, limit + 1e-9)

    def test_slows_down_gradually_without_exceeding_braking(self):
        v = make_vehicle(position=10.0, speed=v_max())
        limit = 120.0
        previous = v.speed
        worst = 0.0
        for _ in range(200):
            drive(v, limit)
            worst = max(worst, (previous - v.speed) / DT)
            previous = v.speed
        # Some slack: the discrete-time rule may brake a little harder than the
        # comfortable value, but nowhere near an emergency stop.
        self.assertLess(worst, CFG.braking * 1.6)
        self.assertLess(v.speed, CFG.halting_speed)
        self.assertLess(limit - v.position, 3.0)

    def test_positions_never_decrease(self):
        v = make_vehicle()
        last = v.position
        for step in range(300):
            drive(v, 100.0 if step < 150 else math.inf)
            self.assertGreaterEqual(v.position, last)
            last = v.position

    def test_completes_after_passing_the_end(self):
        v = make_vehicle(position=END - 1.0, speed=10.0)
        drive(v)
        self.assertTrue(v.completed)

    def test_completed_vehicle_stops_accumulating_time(self):
        v = make_vehicle(position=END, speed=10.0)
        drive(v)
        travel = v.travel_time
        drive(v)
        self.assertEqual(v.travel_time, travel)


class WaitingAndStopTests(unittest.TestCase):
    def test_waiting_time_counts_only_standing_time_before_the_stop_line(self):
        v = make_vehicle(position=STOP_LINE, speed=0.0)
        for _ in range(10):
            drive(v, limit=STOP_LINE)
        self.assertAlmostEqual(v.waiting_time, 10 * DT)
        self.assertTrue(v.stopped)

    def test_no_waiting_time_while_moving(self):
        v = make_vehicle(speed=8.0)
        for _ in range(10):
            drive(v)
        self.assertEqual(v.waiting_time, 0.0)
        self.assertFalse(v.stopped)

    def test_no_waiting_time_after_crossing_the_stop_line(self):
        v = make_vehicle(position=STOP_LINE + 3.0, speed=0.0)
        drive(v, limit=STOP_LINE + 3.0)
        self.assertEqual(v.waiting_time, 0.0)

    def test_travel_time_counts_every_step(self):
        v = make_vehicle()
        for _ in range(8):
            drive(v)
        self.assertAlmostEqual(v.travel_time, 8 * DT)

    def test_one_stop_is_counted_once_however_long_it_lasts(self):
        v = make_vehicle(position=STOP_LINE, speed=0.0)
        for _ in range(50):
            drive(v, limit=STOP_LINE)
        self.assertEqual(v.stops, 1)

    def test_a_second_stop_needs_getting_going_again(self):
        v = make_vehicle(position=STOP_LINE - 30.0, speed=10.0)
        for _ in range(120):
            drive(v, limit=STOP_LINE)  # comes to a halt at the line
        self.assertEqual(v.stops, 1)
        for _ in range(6):
            drive(v)  # light turns green: it drives off (and stays on the road)
        self.assertFalse(v.completed)
        self.assertGreater(v.speed, CFG.halting_speed * 2)
        for _ in range(60):
            drive(v, limit=v.position)  # blocked again: stops a second time
        self.assertEqual(v.stops, 2)

    def test_creeping_forward_slowly_is_not_a_new_stop(self):
        v = make_vehicle(position=50.0, speed=0.0)
        v.stops = 1
        v._armed = False
        for _ in range(30):
            drive(v, limit=v.position + 0.1)  # tiny shuffles
        self.assertEqual(v.stops, 1)

    def test_waiting_outside_the_map_counts_as_waiting_and_one_stop(self):
        v = make_vehicle(position=0.0)
        for _ in range(6):
            v.wait_outside(DT, CFG.halting_speed)
        self.assertAlmostEqual(v.waiting_time, 6 * DT)
        self.assertAlmostEqual(v.travel_time, 6 * DT)
        self.assertEqual(v.stops, 1)


def v_max():
    return CFG.max_speed_ms


if __name__ == "__main__":
    unittest.main()
