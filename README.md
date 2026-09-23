# FastBox Mystery Delivery System

A single-file Python simulator for the Nexgensis Python Developer take-home
assignment. It reads warehouse/agent/package data from JSON, assigns each
package to its nearest agent, simulates one day of deliveries, and writes a
report showing packages delivered, distance travelled, and efficiency per
agent, plus the single most efficient agent overall.

## Requirements

Python 3.8+, standard library only (no third-party packages needed).

## Usage

```bash
# Default: reads ./data.json, writes ./report.json
python delivery_system.py

# Point at a specific input/output file
python delivery_system.py test_case_3.json -o report_3.json

# Bonus extras (all optional, off by default)
python delivery_system.py data.json --ascii-map          # print an ASCII route map
python delivery_system.py data.json --csv top.csv         # export best agent to CSV
python delivery_system.py data.json --delays              # simulate reporting-only delays
```

## Files

- `delivery_system.py` – the whole solution (parsing, assignment, simulation,
  report generation, and the bonus extras), heavily commented.
- `data.json` – the sample input from the assignment brief, included so the
  script runs out of the box.
- `test_case_1.json` … `test_case_10.json`, `base_case.json` – the provided
  test fixtures, kept in the repo so the grader (or anyone else) can rerun
  the script against them directly.

## How it works

1. Parse (`load_json` / `normalize_data`) – reads the JSON file and
   normalizes it into a common internal shape. Two input schemas are
   supported (see Assumption 1 below), since the provided files aren't
   all in the same format.
2. Assign (`assign_packages`) – for every package, computes the
   Euclidean distance from each agent's starting location to that
   package's warehouse, and assigns the package to whichever agent is
   closest.
3. Simulate (`simulate_deliveries`) – walks each agent through its
   assigned packages in input order: travel to the warehouse, pick up,
   travel to the destination, drop off, then treat the drop-off point as
   the agent's new current position for its next package.
4. Report (`build_report`) – totals distance per agent, computes
   `efficiency = total_distance / packages_delivered`, and picks the
   `best_agent` as the one with the *lowest* efficiency (least distance
   per delivery) among agents who delivered at least one package.
5. Save (`save_report`) – writes the report as pretty-printed JSON.

## Assumptions made (per the brief's instruction to document rather than ask)

The brief explicitly says to make a reasonable call on anything ambiguous
and document it rather than stop to ask. Here's every judgment call made,
also repeated as inline comments in the code:

1. Input schema. The brief's own sample and all ten `test_case_*.json`
   files use `{"warehouses": {"W1": [x, y], ...}, "agents": {...},
   "packages": [{"id", "warehouse", "destination"}, ...]}`. The supplied
   `base_case.json` instead uses a list-of-objects schema
   (`{"id", "location"}` and `"warehouse_id"`). The script auto-detects
   and supports both rather than assuming only one is correct.
2. "Nearest agent" is measured agent → warehouse, exactly as the brief
   states, not agent → destination and not warehouse → destination.
3. Ties in nearest-agent distance go to whichever agent appears first
   in the input, for determinism.
4. Routing order within an agent's day: packages are delivered in the
   order they appear in the input file, and the agent's position carries
   over between deliveries (it does not snap back to its starting point
   after every drop-off). This is a simple, deterministic FIFO route
   rather than a travelling-salesman-optimized route, which felt like a
   reasonable "simulate one day of operations" reading without turning a
   take-home assignment into a full route-optimization problem. It's
   naturally not the shortest topologically possible route.
5. Efficiency = total_distance ÷ packages_delivered (average distance
   per delivery). Backed out from the brief's own example numbers, which
   only divide evenly under this definition. An agent with zero
   deliveries gets efficiency `0` rather than a divide-by-zero error.
6. Best agent = lowest efficiency, i.e. the agent covering the least
   distance per package delivered, restricted to agents who delivered at
   least one package. This is also backed out from the brief's example,
   where the agent with the lowest efficiency value is the one labeled
   `best_agent`.
7. All distances are straight-line (Euclidean), never grid/Manhattan,
   and coordinates are unitless plane coordinates.
8. Unknown warehouse references: if a package names a warehouse ID
   that doesn't exist in the input, it's skipped with a printed warning
   rather than crashing the whole run, and the delivered-vs-total sanity
   check will then flag the mismatch.

## Bonus extensions implemented

- ASCII route visualization (`--ascii-map`) – plots each agent's start
  position, pickups, and drop-offs on a text grid.
- Export top performer to CSV (`--csv PATH`) – writes the single most
  efficient agent's stats to a CSV file.
- Simulated random delivery delays (`--delays`) – attaches a seeded,
  reproducible random delay (minutes) to each package for reporting only;
  it never affects distance/efficiency, since the brief's report format
  has no field for it.
- New agent joining mid-day (`apply_new_agent_joins`) – designed but
  intentionally not wired into the main pipeline by default, since none of
  the provided data files define a schema for it. The function documents
  a proposed `"new_agents": [{"id", "location", "after_package"}]` input
  extension and is included so the idea and its data shape are visible in
  the code, without risking the core, graded pipeline on an invented
  schema.

# Testing

The script was run against every provided file (`data.json`, `base_case.json`,
and all ten `test_case_*.json`) with no exceptions, and the
"packages delivered == total packages" sanity check from the brief's notes
passes on every one of them.
