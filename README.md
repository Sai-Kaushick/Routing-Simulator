# Intelligent Network Routing Simulator (NS2 + Python)

A comparative network simulation and analytics dashboard for **RIP (Distance Vector / Bellman-Ford)** and **OSPF (Link State / Dijkstra)** routing protocols.

- **Routing Algorithms:** Implemented in Python for path calculation, metric evaluation, and routing table visualization.
- **Traffic & Packet Simulation:** Simulated natively via **NS2 (Network Simulator 2)** with dynamic routing protocols (`DV` and `LS`) and `$ns rtmodel-at` in-run link failures.
- **Analytics & Metrics:** NS2 trace files are parsed to extract Throughput (kbps), End-to-End Latency (ms), Packet Delivery Ratio (PDR %), Lost Packets, and Recovery Time.
- **Interactive Dashboard:** Built with Streamlit, supporting Topology Presets, Custom Topology Design, Link-Failure Experiments, and Side-by-Side Comparison Charts.

---

## 🚀 Quick Setup for Teammates

### Step 1: Clone or Extract the Project
Open a terminal in the project directory:

```bash
cd "Cn Project"
```

### Step 2: Install Python Dependencies
Python 3.10+ is recommended.

```bash
# Windows (PowerShell)
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Linux / macOS
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Step 3: Install NS2 (Network Simulator 2)

- **On Windows (via WSL2 / Ubuntu - Recommended):**
  1. Open PowerShell and install WSL if not installed:
     ```powershell
     wsl --install -d Ubuntu
     ```
  2. Inside your Ubuntu WSL terminal, install NS2:
     ```bash
     sudo apt update && sudo apt install -y ns2
     ```
  *(The project's `simulation_runner.py` will automatically detect and invoke WSL2 NS2 without any extra configuration).*

- **On Linux (Ubuntu/Debian):**
  ```bash
  sudo apt update && sudo apt install -y ns2
  ```

- **On macOS:**
  Install NS2 via Homebrew or run inside a Docker / Linux container.

---

## 🖥️ Running the Application

Launch the Streamlit web dashboard:

```bash
streamlit run app.py
```

Then open your browser at **http://localhost:8501**.

---

## 🧪 Running the Unit Tests

Run the complete test suite (routing algorithms, trace parsing, boundary cohort tests, failure simulation):

```bash
python -m unittest discover -s tests -v
```

---

## 📂 Project Structure

```
Cn Project/
├── app.py                      # Main Streamlit web application & dashboards
├── requirements.txt            # Python dependencies
├── .gitignore                  # Git ignore rules (excludes .venv, traces)
│
├── topology/
│   ├── graph_manager.py        # 4-node diamond, 6-node mesh, 8-node ring, custom builder
│   └── __init__.py
│
├── routing/
│   ├── rip.py                  # Bellman-Ford shortest path (hop-count metric)
│   ├── ospf.py                 # Dijkstra shortest path (link-cost metric)
│   └── __init__.py
│
├── ns2/
│   ├── simulation_runner.py    # Subprocess execution (native NS2 or via WSL2)
│   ├── tcl_generator.py        # Generates NS2 Tcl scripts (rtproto DV/LS & rtmodel-at)
│   ├── trace_parser.py         # Parses NS2 .tr trace logs using cohort tracking
│   └── __init__.py
│
├── analysis/
│   ├── comparison.py           # Protocol comparison runner & failure experiment manager
│   ├── recommendation.py       # Rule-based heuristics for protocol recommendations
│   ├── experiment.py           # CSV and JSON results logger
│   └── __init__.py
│
├── visualization/
│   ├── charts.py               # Grouped bar charts, failure comparisons, heatmaps
│   └── __init__.py
│
├── events/
│   ├── failure_simulator.py    # Graph mutation helpers for link failure
│   └── __init__.py
│
├── results/                    # Auto-generated simulation outputs (.tr, .tcl, .csv, .json)
└── tests/                      # Automated unit test suite
```

---

## 💡 Key Features to Demonstrate

1. **Preset & Custom Topologies:**
   - Switch between **4-Router Diamond**, **6-Router Mesh**, **8-Router Backbone Ring**, or use the **Interactive Builder** to design any custom network.
2. **RIP vs OSPF Routing Divergence:**
   - On the 6-Router Mesh, show how RIP chooses a 2-hop slow link (`500Kb`) while OSPF chooses a 3-hop high-speed path (`2Mb`).
3. **In-Run Link Failure Simulation:**
   - Toggle link failures (`$ns rtmodel-at`) to observe real packet drops and convergence recovery gap.
4. **Side-by-Side Comparison Charts:**
   - Compare throughput, delay, PDR, and loss side-by-side with color-coded bar charts.
