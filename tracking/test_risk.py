"""Self-test for risk.py using scripted tracks (no video or AI needed). Run: python test_risk.py"""
from risk import RiskEngine, RiderFinder

FPS = 25


def trk(tid, cls, x, y, w, h, vx=0.0, vy=0.0):
    """A track whose box bottom-center is (x, y) and which moves (vx, vy) pixels per second."""
    return {"tid": tid, "cls": cls, "x1": x - w / 2, "y1": y - h, "x2": x + w / 2, "y2": y, "gx": x, "gy": y,
            "vx": vx, "vy": vy, "speed": (vx ** 2 + vy ** 2) ** 0.5, "age": 99}


def run(frames, zones=None):
    eng, events = RiskEngine(zones or {}, FPS), []
    for f, tracks in enumerate(frames):
        events += eng.update(f, f / FPS, tracks)
    return events, eng


def kinds(events): return [(e["type"], e["severity"]) for e in events]


# 1) car passes a pedestrian, feet 24 px apart at 300 px/s: near miss, once, no collision
ev, _ = run([[trk(1, "car", 20 + 12 * f, 500, 120, 70, 300), trk(2, "person", 300, 455, 30, 80)] for f in range(60)])
print("near pass     :", kinds(ev)); assert [e["type"] for e in ev].count("NEAR_MISS") == 1 and "POSSIBLE_COLLISION" not in [e["type"] for e in ev] and len(ev) <= 2, ev
# 2) car drives straight into the pedestrian: possible collision
ev, _ = run([[trk(1, "car", 20 + 12 * f, 500, 120, 70, 300), trk(2, "person", 300, 500, 30, 80)] for f in range(40)])
types = [e["type"] for e in ev]
print("direct hit    :", types); assert types.count("POSSIBLE_COLLISION") == 1 and types.index("POSSIBLE_COLLISION") == len(types) - 1
# 3) two cars side by side, far apart, same speed: nothing
ev, _ = run([[trk(1, "car", 100 + 8 * f, 500, 120, 70, 200), trk(2, "car", 100 + 8 * f, 250, 120, 70, 200)] for f in range(60)])
print("parallel cars :", kinds(ev)); assert ev == []
# 4) a rider on a motorbike (person box inside the bike box, moving together): nothing
ev, _ = run([[trk(1, "bike", 100 + 8 * f, 500, 60, 90, 200), trk(2, "person", 100 + 8 * f, 480, 30, 70, 200)] for f in range(60)])
print("rider on bike :", kinds(ev)); assert ev == []
# 5) pedestrian crossing in front of a moving car (not yet close): pedestrian risk
ev, _ = run([[trk(1, "car", 20 + 6 * f, 500, 120, 70, 150), trk(2, "person", 400, 500 - 0.5 * f, 30, 80, 0, -12)] for f in range(60)])
print("crossing ahead:", [e["type"] for e in ev]); assert len(ev) >= 1 and len({e["type"] for e in ev}) == len(ev)   # never the same type twice
# 6) sudden braking: 400 px/s then down to 100 px/s within 0.4 s; gentle slowing does nothing
def speed_at(f, hard):
    if f < 20: return 400
    return max(100, 400 - (750 if hard else 60) * (f - 20) / FPS)
def braking(hard):
    x, frames = 0.0, []
    for f in range(60):
        v = speed_at(f, hard); x += v / FPS
        frames.append([trk(1, "car", x, 500, 120, 70, v)])
    return run(frames)[0]
ev = braking(True); print("hard braking  :", kinds(ev)); assert kinds(ev) == [("SUDDEN_BRAKE", "MEDIUM")]
ev = braking(False); print("gentle slowing:", kinds(ev)); assert ev == []
# 7) lane change across a vertical lane line at x=500: fast sideways move yes, slow drift no
zones = {"lane_lines": [{"points": [[500, 0], [500, 720]]}]}
fast, _ = run([[trk(1, "car", 400 + 6 * f, 500 - 3 * f, 120, 70, 150, -75)] for f in range(40)], zones)
slow, _ = run([[trk(1, "car", 480 + 0.8 * f, 500 - 3 * f, 120, 70, 20, -75)] for f in range(40)], zones)
print("lane change   :", kinds(fast), "| slow drift:", kinds(slow)); assert [e["type"] for e in fast] == ["LANE_CHANGE"] and slow == []
# 8) congestion: 20 stopped vehicles -> HIGH once, after a hold time (not instantly)
crowd = [[trk(i, "car", 50 + 60 * (i % 10), 300 + 90 * (i // 10), 50, 40) for i in range(20)] for _ in range(250)]
ev, eng = run(crowd); print("congestion    :", kinds(ev), "level", eng.level); assert kinds(ev) == [("CONGESTION", "HIGH")] and eng.level == "HIGH" and ev[0]["frame"] > 50
# 9) a car stopped behind another: the boxes overlap in the picture (perspective) but the feet do not touch: nothing
ev, _ = run([[trk(1, "car", 300, 500, 120, 100), trk(2, "car", 300, 440, 90, 70, 0, 20)] for f in range(60)])
print("queue overlap :", kinds(ev)); assert ev == []
# 10) a two-frame glitch (objects look very close for only 2 frames): no event
glitch = [[trk(1, "car", 230 if f in (10, 11) else 20, 500, 120, 70, 300 if f in (10, 11) else -300), trk(2, "person", 300, 455, 30, 80)] for f in range(30)]
ev, _ = run(glitch); print("2-frame glitch:", kinds(ev)); assert ev == []
# 11) brand-new tracks (age 3) are ignored
young = [[{**trk(1, "car", 20 + 12 * f, 500, 120, 70, 300), "age": 3}, {**trk(2, "person", 300, 500, 30, 80), "age": 3}] for f in range(40)]
ev, _ = run(young); print("new tracks    :", kinds(ev)); assert ev == []
# 12) riders: a person on a moving bike becomes a rider within 2 frames; a pedestrian beside a parked bike does not
rf = RiderFinder(); out = []
for f in range(6):
    x = 100 + 12 * f
    out.append(rf.update([{**trk(1, "bike", x, 500, 60, 90, 300)}, {**trk(2, "person", x, 480, 40, 100, 300)},
                          {**trk(3, "person", 400, 500, 30, 80, 0)}]))
print("rider on bike :", [sorted(o) for o in out]); assert out[0] == set() and out[-1] == {2}, out
# 13) a "person" moving far too fast to be walking (the bike was not detected) is treated as a rider; a walker is not
rf = RiderFinder()
for f in range(6):
    r = rf.update([trk(4, "person", 100 + 14 * f, 500, 30, 80, 350), trk(5, "person", 300, 500, 30, 80, 70)])
print("fast / walking:", sorted(r)); assert r == {4}
# 14) a rider fades back to pedestrian once they are no longer on a bike, and a car near a rider raises no pedestrian event
for f in range(12):
    r = rf.update([trk(4, "person", 100, 500, 30, 80, 0)])
assert r == set(), r
eng, ev = RiskEngine({}, FPS), []
rf = RiderFinder()
for f in range(60):
    tracks = [trk(1, "car", 20 + 12 * f, 500, 120, 70, 300), trk(2, "bike", 300, 500, 60, 90), trk(3, "person", 300, 480, 40, 100)]
    riders = rf.update(tracks)
    ev += eng.update(f, f / FPS, [a for a in tracks if a["tid"] not in riders])
print("car near rider:", sorted({e["type"] for e in ev})); assert ev and not any("Ped" in e["objects"] for e in ev)
print("ALL TESTS PASSED")
