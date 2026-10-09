// Real recorded v2 session: commands, exact output, exit codes and wall times.
// Recorded by running each command in bash; nothing here is edited.
window.SESSION = {
 "recorded": "2026-10-09",
 "environment": "Debian 13 container, conda-forge FreeCAD 1.0.0, OCC 7.8.1, Python 3.13.5; unmodified printkit runtime gate",
 "session": [
  {
   "command": "python -m printkit check-intent plate/intent.json | jq '{measured_checks, person_checks, unknowns}'",
   "output": "{\n  \"measured_checks\": [\n    \"envelope\",\n    \"solid_count\",\n    \"screw-hole-1\",\n    \"screw-hole-2\",\n    \"screw-hole-3\",\n    \"screw-hole-4\",\n    \"flat-bottom\"\n  ],\n  \"person_checks\": [\n    \"rounded-corners\"\n  ],\n  \"unknowns\": [\n    \"corner radius\",\n    \"screw head type (countersunk or pan)\",\n    \"printer and material\",\n    \"load on the plate\"\n  ]\n}",
   "stderr": "",
   "exit": 0,
   "seconds": 0.07
  },
  {
   "command": "python -m printkit check-plan plate/plan-001.json --intent plate/intent.json | jq -c '{status, step_count, warnings}'",
   "output": "{\"status\":\"pass\",\"step_count\":6,\"warnings\":[]}",
   "stderr": "",
   "exit": 0,
   "seconds": 0.07
  },
  {
   "command": "python -m printkit build --intent plate/intent.json --plan plate/plan-001.json --output runs/plate-001 | jq -r .overall_state",
   "output": "blocked",
   "stderr": "",
   "exit": 4,
   "seconds": 6.67
  },
  {
   "command": "jq -r '.conformance.checks[] | select(.code != \"unknown\") | \"\\(.status)\\t\\(.code)\"' runs/plate-001/report.json",
   "output": "pass\tnative_solid\npass\tenvelope\npass\tfeature:screw-hole-1\nfail\tfeature:screw-hole-2\npass\tfeature:screw-hole-3\nfail\tfeature:screw-hole-4\npass\tfeature:flat-bottom\nneeds_review\tfeature:rounded-corners\nneeds_review\tunrequested_holes",
   "stderr": "",
   "exit": 0,
   "seconds": 0.01
  },
  {
   "command": "jq -c '.conformance.checks[] | select(.code == \"feature:screw-hole-2\") | .actual' runs/plate-001/report.json",
   "output": "{\"nearest_hole\":{\"diameter_mm\":4.0,\"position_mm\":[52.0,6.000000000000001]}}",
   "stderr": "",
   "exit": 0,
   "seconds": 0.01
  },
  {
   "command": "diff plate/plan-001.json plate/plan-002.json",
   "output": "39c39\n<         46,\n---\n>         48,",
   "stderr": "",
   "exit": 1,
   "seconds": 0.0
  },
  {
   "command": "python -m printkit build --intent plate/intent.json --plan plate/plan-002.json --output runs/plate-002 | jq -r .overall_state",
   "output": "needs_review",
   "stderr": "",
   "exit": 5,
   "seconds": 6.72
  },
  {
   "command": "jq -r '.conformance.checks[] | select(.code != \"unknown\") | \"\\(.status)\\t\\(.code)\"' runs/plate-002/report.json",
   "output": "pass\tnative_solid\npass\tenvelope\npass\tfeature:screw-hole-1\npass\tfeature:screw-hole-2\npass\tfeature:screw-hole-3\npass\tfeature:screw-hole-4\npass\tfeature:flat-bottom\nneeds_review\tfeature:rounded-corners\npass\tunrequested_holes",
   "stderr": "",
   "exit": 0,
   "seconds": 0.01
  },
  {
   "command": "jq -c .person_checks runs/plate-002/report.json",
   "output": "[\"feature:rounded-corners\",\"five_view_review\",\"print_settings\",\"physical_test\"]",
   "stderr": "",
   "exit": 0,
   "seconds": 0.01
  }
 ]
};
