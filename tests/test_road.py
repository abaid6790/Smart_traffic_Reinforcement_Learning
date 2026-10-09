import unittest

from config.settings import SimulationConfig
from environment.enums import Direction, SignalColor
from environment.road import Road
from environment.vehicle import Vehicle

CFG = SimulationConfig()
DT = CFG.dt


def make_vehicle(vid=1, **kwargs):
    defaults = dict(id=vid, direction=Direction.NORTH, max_speed=CFG.max_speed_ms,
                    length=CFG.vehicle_length)
    defaults.update(kwargs)
    return Vehicle(**defaults)


def place(road, vehicle, position, speed=0.0):
    vehicle.position, vehicle.speed, vehicle.entered = position, speed, True
    road.vehicles.append(vehicle)
    road.vehicles.sort(key=lambda v: -v.position)
    return vehicle


def run(road, seconds, signal):
    done = []
    for _ in range(int(round(seconds / DT))):
        done.extend(road.step(DT, signal))
    return done


class RoadTests(unittest.TestCase):
    def setUp(self):
        self.road = Road(Direction.NORTH, CFG)

    def test_geometry(self):
        self.assertEqual(self.road.stop_line, CFG.road_length)
        self.assertEqual(self.road.box_end, CFG.road_length + CFG.intersection_length)

    def test_arrival_enters_the_road(self):
        self.road.add_arrival(make_vehicle())
        self.road.step(DT, SignalColor.GREEN)
        self.assertEqual(self.road.vehicle_count(), 1)
        self.assertTrue(self.road.vehicles[0].entered)
        self.assertEqual(len(self.road.backlog), 0)

    def test_vehicle_stops_at_red_light_before_the_line(self):
        v = place(self.road, make_vehicle(), 100.0, speed=CFG.max_speed_ms)
        run(self.road, 60, SignalColor.RED)
        self.assertLessEqual(v.position, self.road.stop_line + 1e-6)
        self.assertGreater(v.position, self.road.stop_line - 3.0)
        self.assertLess(v.speed, CFG.halting_speed)
        self.assertTrue(v.stopped)

    def test_vehicle_moves_and_leaves_on_green(self):
        v = place(self.road, make_vehicle(), 100.0, speed=CFG.max_speed_ms)
        done = run(self.road, 60, SignalColor.GREEN)
        self.assertEqual(done, [v])
        self.assertTrue(v.completed)
        self.assertEqual(self.road.vehicle_count(), 0)
        self.assertEqual(v.waiting_time, 0.0)

    def test_stopped_queue_discharges_when_light_turns_green(self):
        vehicles = [place(self.road, make_vehicle(i), self.road.stop_line - i * 6.5, 0.0)
                    for i in range(1, 6)]
        run(self.road, 10, SignalColor.RED)
        self.assertEqual(self.road.queue_length(), 5)
        self.assertTrue(all(v.waiting_time > 0 for v in vehicles))
        done = run(self.road, 60, SignalColor.GREEN)
        self.assertEqual(len(done), 5)

    def test_vehicle_that_cannot_stop_on_yellow_goes_through(self):
        v = place(self.road, make_vehicle(), self.road.stop_line - 4.0, speed=CFG.max_speed_ms)
        run(self.road, 20, SignalColor.YELLOW)
        self.assertTrue(v.completed)

    def test_vehicle_that_can_stop_on_yellow_stops(self):
        v = place(self.road, make_vehicle(), 60.0, speed=CFG.max_speed_ms)
        run(self.road, 40, SignalColor.YELLOW)
        self.assertLessEqual(v.position, self.road.stop_line + 1e-6)
        self.assertFalse(v.completed)

    def test_vehicle_already_past_the_line_keeps_going_on_red(self):
        v = place(self.road, make_vehicle(), self.road.stop_line + 3.0, speed=8.0)
        run(self.road, 20, SignalColor.RED)
        self.assertTrue(v.completed)

    def test_followers_keep_a_gap_and_never_overlap(self):
        leader = place(self.road, make_vehicle(1), 150.0, speed=0.0)
        follower = place(self.road, make_vehicle(2), 60.0, speed=CFG.max_speed_ms)
        for _ in range(240):
            self.road.step(DT, SignalColor.RED)
            self.assertGreaterEqual(leader.rear - follower.position, CFG.min_gap - 1e-6)

    def test_queue_length_counts_only_standing_vehicles_before_the_line(self):
        place(self.road, make_vehicle(1), self.road.stop_line - 1.0, 0.0)
        place(self.road, make_vehicle(2), 80.0, CFG.max_speed_ms)
        place(self.road, make_vehicle(3), self.road.stop_line + 4.0, 0.0)
        self.assertEqual(self.road.queue_length(), 1)
        self.assertEqual(self.road.approach_count(), 2)

    def test_backlog_counts_in_queue_and_waits_without_vanishing(self):
        # Fill the road with a stopped queue reaching back to the entrance.
        position, vid = self.road.stop_line, 1
        while position - CFG.vehicle_length >= 0.0:
            place(self.road, make_vehicle(vid), position, 0.0)
            position -= CFG.vehicle_length + CFG.min_gap
            vid += 1
        queued = self.road.vehicle_count()
        self.road.add_arrival(make_vehicle(999))
        run(self.road, 5, SignalColor.RED)
        self.assertEqual(len(self.road.backlog), 1)  # no room: it waits outside
        self.assertEqual(self.road.queue_length(), queued + 1)
        self.assertAlmostEqual(self.road.backlog[0].waiting_time, 5.0)
        # Once the light turns green the queue drains and the vehicle gets in.
        run(self.road, 40, SignalColor.GREEN)
        self.assertEqual(len(self.road.backlog), 0)

    def test_has_vehicle_in_box(self):
        self.assertFalse(self.road.has_vehicle_in_box())
        place(self.road, make_vehicle(), self.road.stop_line - 1.0)
        self.assertFalse(self.road.has_vehicle_in_box())
        self.road.vehicles[0].position = self.road.stop_line + 5.0
        self.assertTrue(self.road.has_vehicle_in_box())
        self.road.vehicles[0].position = self.road.box_end + CFG.vehicle_length + 1.0
        self.assertFalse(self.road.has_vehicle_in_box())

    def test_reset_empties_the_road(self):
        place(self.road, make_vehicle(1), 50.0)
        self.road.add_arrival(make_vehicle(2))
        self.road.reset()
        self.assertEqual((self.road.vehicle_count(), len(self.road.backlog)), (0, 0))


if __name__ == "__main__":
    unittest.main()
