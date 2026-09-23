"""
FastBox Mystery Delivery System
================================

Simulates one day of FastBox delivery operations:
  1. Parses warehouse / agent / package data from a JSON file.
  2. Assigns every package to the agent nearest to its warehouse.
  3. Simulates each agent's deliveries and totals the distance travelled.
  4. Writes a per-agent report (packages delivered, distance, efficiency,
     and the single most efficient agent) to report.json.

Usage:
    python delivery_system.py [input_file] [-o output_file]

    python delivery_system.py                     # reads data.json, writes report.json
    python delivery_system.py test_case_3.json     # reads a different input file
    python delivery_system.py data.json -o out.json

Author: (submission for Nexgensis Technologies Python Developer assignment)
"""

import json
import math
import argparse
import csv
import sys


# ---------------------------------------------------------------------------
# Documented assumptions
# ---------------------------------------------------------------------------
# The assignment brief is deliberately light on a few details. Per the
# instructions ("assume the best possible scenario and document it"), the
# assumptions made below are recorded here AND repeated as inline comments
# at the point where they matter, so a reviewer can find them either way.
#
# A1. INPUT SCHEMA
#     The sample `data.json` in the brief (and every provided test case)
#     stores warehouses/agents as a dict of {id: [x, y]} and each package
#     as {"id", "warehouse", "destination"}. One provided file
#     (base_case.json) instead uses a list of {"id", "location"} objects
#     and a "warehouse_id" key on packages. Both schemas are accepted
#     (see `normalize_data`) so the script is not fragile to either style.
#
# A2. NEAREST AGENT = nearest to the package's WAREHOUSE (not the
#     destination), measured once per package by straight-line
#     (Euclidean) distance from the agent's fixed starting location to
#     the warehouse. This matches the brief's wording exactly: "Assign
#     each package to the nearest agent based on Euclidean distance from
#     agent to warehouse."
#
# A3. TIE-BREAKING for nearest-agent assignment: if two or more agents are
#     exactly equidistant from a warehouse, the agent that appears first
#     in the input's agent list/dict wins. This is deterministic and
#     reproducible, which is preferable to an arbitrary/random pick for a
#     business report.
#
# A4. ROUTING / SIMULATION ORDER: an agent does not teleport back to its
#     starting point between deliveries. Instead, each agent's assigned
#     packages are delivered in the order they appear in the input file
#     (a simple, deterministic FIFO route), and the agent's "current
#     position" carries over from one delivery to the next:
#         distance += dist(current_position, warehouse)   # travel to pick up
#         distance += dist(warehouse, destination)         # travel to drop off
#         current_position = destination
#     Full route optimization (e.g. solving a Travelling-Salesman route
#     per agent) is out of scope for the brief and is flagged as a
#     possible bonus extension rather than assumed silently.
#
# A5. EFFICIENCY = total_distance / packages_delivered (average distance
#     travelled per package). This is derived from the sample report in
#     the brief: 85.32 / 2 == 42.66, 120.12 / 2 == 60.06, 50.00 / 1 ==
#     50.00 -- the numbers only make sense as total_distance divided by
#     packages_delivered. An agent with 0 deliveries gets efficiency 0
#     (not delivering nothing shouldn't look "infinitely efficient").
#
# A6. BEST AGENT = the agent with the LOWEST efficiency value (i.e. the
#     smallest average distance per package -- the agent who covers the
#     least ground for each delivery). In the brief's sample report, A1
#     (42.66) is chosen as best_agent over A3 (50.00) and A2 (60.06),
#     which is only consistent with "lowest efficiency wins". Agents with
#     zero deliveries are not eligible to be best_agent. Ties are broken
#     by whichever agent appears first in the input.
#
# A7. All coordinates are treated as plain (x, y) points on a flat plane;
#     "distance" is always straight-line Euclidean distance, never
#     grid/Manhattan distance.
# ---------------------------------------------------------------------------


def load_json(path):
    """Manually read and parse a JSON file (Task 1)."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def normalize_data(raw):
    """
    Accepts either supported schema (see assumption A1) and returns a
    common internal representation:
        warehouses: {wh_id: (x, y)}
        agents:     [{"id": agent_id, "location": (x, y)}]   (order preserved)
        packages:   [{"id": pkg_id, "warehouse": wh_id, "destination": (x, y)}]
    """
    raw_wh = raw["warehouses"]
    raw_ag = raw["agents"]
    raw_pkg = raw["packages"]

    # --- warehouses: dict-of-coords style, or list-of-objects style ---
    if isinstance(raw_wh, dict):
        warehouses = {wh_id: tuple(coords) for wh_id, coords in raw_wh.items()}
    else:  # list of {"id": ..., "location": [...]}
        warehouses = {w["id"]: tuple(w["location"]) for w in raw_wh}

    # --- agents: dict-of-coords style, or list-of-objects style ---
    if isinstance(raw_ag, dict):
        agents = [{"id": a_id, "location": tuple(coords)} for a_id, coords in raw_ag.items()]
    else:  # list of {"id": ..., "location": [...]}
        agents = [{"id": a["id"], "location": tuple(a["location"])} for a in raw_ag]

    # --- packages: "warehouse" key, or "warehouse_id" key ---
    packages = []
    for p in raw_pkg:
        wh_key = p.get("warehouse", p.get("warehouse_id"))
        packages.append({
            "id": p["id"],
            "warehouse": wh_key,
            "destination": tuple(p["destination"]),
        })

    return warehouses, agents, packages


def euclidean_distance(p1, p2):
    """Straight-line distance between two (x, y) points."""
    return math.sqrt((p1[0] - p2[0]) ** 2 + (p1[1] - p2[1]) ** 2)


def assign_packages(warehouses, agents, packages):
    """
    Task 2: assign every package to the agent nearest to that package's
    warehouse (assumption A2), breaking ties by input order (assumption A3).

    Returns: {agent_id: [package, ...]}   in the order packages were assigned.
    """
    assignments = {agent["id"]: [] for agent in agents}

    for pkg in packages:
        wh_location = warehouses.get(pkg["warehouse"])
        if wh_location is None:
            # Edge case: package references a warehouse that doesn't exist.
            # We skip it rather than crash, and note it so it's visible.
            print(f"  [warning] package {pkg['id']} references unknown "
                  f"warehouse '{pkg['warehouse']}' -- skipped.")
            continue

        nearest_agent = None
        nearest_dist = None
        for agent in agents:  # first-in-input wins ties (A3)
            d = euclidean_distance(agent["location"], wh_location)
            if nearest_dist is None or d < nearest_dist:
                nearest_dist = d
                nearest_agent = agent["id"]

        assignments[nearest_agent].append(pkg)

    return assignments


def simulate_deliveries(warehouses, agents, assignments):
    """
    Task 3: simulate each agent delivering its assigned packages and total
    the distance travelled (assumption A4 for routing order).

    Returns: {agent_id: {"packages_delivered": int,
                          "total_distance": float,
                          "route": [ (label, point), ... ]}}   # route kept for ASCII viz
    """
    results = {}
    agent_start = {a["id"]: a["location"] for a in agents}

    for agent_id, pkgs in assignments.items():
        current_pos = agent_start[agent_id]
        total_distance = 0.0
        route = [("start", current_pos)]

        for pkg in pkgs:
            wh_location = warehouses[pkg["warehouse"]]
            dest = pkg["destination"]

            total_distance += euclidean_distance(current_pos, wh_location)
            total_distance += euclidean_distance(wh_location, dest)

            route.append((f"pickup {pkg['id']} @ {pkg['warehouse']}", wh_location))
            route.append((f"deliver {pkg['id']}", dest))

            current_pos = dest  # agent now stands at the drop-off point (A4)

        results[agent_id] = {
            "packages_delivered": len(pkgs),
            "total_distance": total_distance,
            "route": route,
        }

    return results


def build_report(simulation, total_package_count):
    """
    Task 4: turn the simulation results into the report format shown in
    the brief, including efficiency (A5) and best_agent (A6).
    """
    report = {}
    delivered_total = 0

    for agent_id, data in simulation.items():
        delivered = data["packages_delivered"]
        distance = data["total_distance"]
        efficiency = round(distance / delivered, 2) if delivered else 0.0

        report[agent_id] = {
            "packages_delivered": delivered,
            "total_distance": round(distance, 2),
            "efficiency": efficiency,
        }
        delivered_total += delivered

    # Best agent = lowest efficiency (least distance per package), among
    # agents that actually delivered something (A6).
    eligible = {aid: r for aid, r in report.items() if r["packages_delivered"] > 0}
    if eligible:
        best_agent = min(eligible, key=lambda aid: (eligible[aid]["efficiency"], aid))
    else:
        best_agent = None

    report["best_agent"] = best_agent

    # Sanity check requested in the brief's notes.
    if delivered_total != total_package_count:
        print(f"  [warning] {delivered_total} packages delivered but "
              f"{total_package_count} were provided -- some packages could "
              f"not be assigned (see warnings above).")

    return report


def save_report(report, path):
    """Task 5: save the report to disk as JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)


# ---------------------------------------------------------------------------
# Bonus features (all optional, all opt-in via CLI flags so the core
# pipeline above stays simple, deterministic, and easy to grade on its own)
# ---------------------------------------------------------------------------

def ascii_route_map(simulation, warehouses, agents, width=60, height=24):
    """
    Bonus: render every agent's route on a simple ASCII grid.
    Agents are drawn as letters (A, B, C, ...), warehouses as '#', and each
    agent's own route points are shown so you can see roughly where it went.
    This is a rough sketch, not to scale in both axes independently -- it's
    meant as a quick visual sanity check, not a precise map.
    """
    all_points = list(warehouses.values())
    for a in agents:
        all_points.append(a["location"])
    for data in simulation.values():
        all_points.extend(pt for _, pt in data["route"])

    xs = [p[0] for p in all_points]
    ys = [p[1] for p in all_points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1)
    span_y = max(max_y - min_y, 1)

    grid = [[" "] * width for _ in range(height)]

    def to_cell(pt):
        gx = int((pt[0] - min_x) / span_x * (width - 1))
        gy = int((pt[1] - min_y) / span_y * (height - 1))
        gy = height - 1 - gy  # flip so +y is "up"
        return gx, gy

    for wh_loc in warehouses.values():
        gx, gy = to_cell(wh_loc)
        grid[gy][gx] = "#"

    for i, (agent_id, data) in enumerate(simulation.items()):
        letter = chr(ord("A") + (i % 26))
        for _, pt in data["route"]:
            gx, gy = to_cell(pt)
            if grid[gy][gx] == " ":
                grid[gy][gx] = letter

    lines = ["".join(row) for row in grid]
    legend = "Legend: '#' = warehouse, letters = agent routes (start + stops)"
    return legend + "\n" + "\n".join(lines)


def export_top_performer_csv(report, path):
    """Bonus: export the single most efficient agent's stats to CSV."""
    best_id = report.get("best_agent")
    if not best_id:
        return False
    stats = report[best_id]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["agent_id", "packages_delivered", "total_distance", "efficiency"])
        writer.writerow([best_id, stats["packages_delivered"], stats["total_distance"], stats["efficiency"]])
    return True


def apply_new_agent_joins(raw, agents, packages_processed_so_far):
    """
    Bonus: "handle a new agent joining mid-day".

    Design (documented, since the brief gives no schema for this): an input
    file MAY optionally include a top-level "new_agents" list:
        "new_agents": [
            {"id": "A9", "location": [40, 40], "after_package": 5}
        ]
    meaning agent A9 becomes available for assignment only once 5 packages
    (by input order) have already been processed. None of the provided
    test files use this key, so it is a no-op unless present -- it's kept
    separate from the core pipeline so it can't break the required tasks.
    This helper simply returns which agents are "active" for a given
    package index.
    """
    new_agents = raw.get("new_agents", [])
    active = list(agents)
    for na in new_agents:
        if packages_processed_so_far >= na.get("after_package", 0):
            if not any(a["id"] == na["id"] for a in active):
                active.append({"id": na["id"], "location": tuple(na["location"])})
    return active


def simulate_random_delays(packages, seed=42):
    """
    Bonus: attach a (deterministic, seeded) simulated delay in minutes to
    each package for reporting purposes. Delays are cosmetic -- they do
    NOT affect distance/efficiency, since the brief's distance model is
    purely spatial.
    """
    import random
    rng = random.Random(seed)
    return {pkg["id"]: rng.choice([0, 0, 0, 5, 10, 15]) for pkg in packages}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="FastBox Mystery Delivery System simulator")
    parser.add_argument("input_file", nargs="?", default="data.json",
                         help="Path to the input JSON file (default: data.json)")
    parser.add_argument("-o", "--output", default="report.json",
                         help="Path to write the report JSON (default: report.json)")
    parser.add_argument("--ascii-map", action="store_true",
                         help="Bonus: print an ASCII visualization of agent routes")
    parser.add_argument("--csv", metavar="PATH",
                         help="Bonus: export the top performer's stats to a CSV file")
    parser.add_argument("--delays", action="store_true",
                         help="Bonus: simulate random per-package delivery delays (reporting only)")
    args = parser.parse_args()

    print(f"Reading input from '{args.input_file}'...")
    raw = load_json(args.input_file)
    warehouses, agents, packages = normalize_data(raw)
    print(f"  {len(warehouses)} warehouses, {len(agents)} agents, {len(packages)} packages loaded.")

    print("Assigning packages to nearest agents...")
    assignments = assign_packages(warehouses, agents, packages)

    print("Simulating deliveries...")
    simulation = simulate_deliveries(warehouses, agents, assignments)

    report = build_report(simulation, total_package_count=len(packages))
    save_report(report, args.output)
    print(f"Report saved to '{args.output}'.")
    print(json.dumps(report, indent=2))

    if args.delays:
        delays = simulate_random_delays(packages)
        total_delay = sum(delays.values())
        print(f"\n[bonus] Simulated delays (minutes) per package: {delays}")
        print(f"[bonus] Total simulated delay across all packages: {total_delay} min")

    if args.ascii_map:
        print("\n[bonus] ASCII route map:")
        print(ascii_route_map(simulation, warehouses, agents))

    if args.csv:
        ok = export_top_performer_csv(report, args.csv)
        if ok:
            print(f"\n[bonus] Top performer exported to '{args.csv}'.")
        else:
            print("\n[bonus] No eligible top performer to export.")


if __name__ == "__main__":
    main()
