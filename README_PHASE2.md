# Phase 2: NS2 failures, routing changes, and recovery measurements

This patch adds the next milestone to the Intelligent Network Routing Simulator:
- event-aware link failure configuration
- two-phase experiment (pre-failure and post-failure)
- route recomputation after a failed link
- trace parser improvements and recovery-time reporting
- comparison-ready metrics output

## Important scope
This is still a controlled experiment, not a native RIP/OSPF implementation inside NS2. Python computes each route; Tcl/NS2 executes traffic over the selected path in separate phases. Recovery time is measured as the outage between the configured failure time and the restart of the post-failure traffic phase. It is therefore **application recovery under this experiment model**, not protocol convergence time.

## Apply the patch
Copy these files/folders into your existing project, allowing replacement when prompted:
- `app.py`
- `ns2/tcl_generator.py`
- `ns2/simulation_runner.py`
- `ns2/trace_parser.py`
- `events/failure_simulator.py`
- `analysis/experiment.py`
- `tests/test_experiment.py`

Keep your other files unchanged.

## Run
```powershell
python -m unittest discover -s tests -v
python -m streamlit run app.py
```

The app can generate a single-phase simulation or a link-failure experiment. To run NS2 measurements, `ns` must be installed and available in the environment that launches Streamlit. On Windows, use a compatible Linux/WSL environment if needed.
