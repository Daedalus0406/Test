# Workstation Control Interface

An integrated desktop application for controlling PLC-connected workstation devices, replacing Node-RED + InfluxDB.

## Features

- **Control Panel** - ON/OFF control and setpoint adjustment for pumps, motors, heaters
- **Real-time Trend Charts** - Live Temperature, Pressure, Flow rate plots (1-second update)
- **Data Recording** - Export to Excel files with organized date folders
- **History Viewer** - Load and visualize previously recorded data
- **JSON Configuration** - Flexible setup for different workstation configurations
- **Modbus TCP** - Direct Ethernet communication with PLCs

## Quick Start

### Install Dependencies

```bash
pip install -r requirements.txt
```

### Run with Config Selector

```bash
python main.py
```

### Run with Specific Config

```bash
python main.py -c config/station_2pumps.json
```

### Simulation Mode (no PLC required)

```bash
python main.py --simulate -c config/station_2pumps.json
```

## Project Structure

```
workstation_control/
├── main.py                     # Application entry point
├── requirements.txt            # Python dependencies
├── config/
│   ├── station_2pumps.json     # Example: 2-pump workstation
│   └── station_3pumps.json     # Example: 3-pump workstation
├── core/
│   ├── config_loader.py        # JSON config validation & loading
│   ├── modbus_client.py        # Modbus TCP communication with PLC
│   └── data_recorder.py        # Excel file recording engine
└── ui/
    ├── main_window.py          # Main application window
    ├── control_panel.py        # Device control cards & sensor display
    ├── trend_chart.py          # Real-time pyqtgraph trend plots
    └── history_viewer.py       # Historical data viewer dialog
```

## Configuration

Config files are JSON format. See `config/` for examples.

### Key Sections

| Section | Description |
|---------|-------------|
| `station_name` | Display name for the workstation |
| `plc` | PLC connection settings (host, port, unit_id) |
| `poll_interval_ms` | Sensor polling interval (default: 1000ms) |
| `devices` | List of controllable devices (pump/motor/heater) |
| `sensors` | List of sensor inputs (Temperature/Pressure/Flow) |

### Device Types

| Type | Controls |
|------|----------|
| `pump` | ON/OFF + RPM setpoint |
| `motor` | ON/OFF + Hz setpoint |
| `heater` | ON/OFF + °C setpoint |

### Sensor Data Types

Supported register data types: `uint16`, `int16`, `int32`, `float32`

Values are converted: `engineering_value = raw * scale + offset`

## Data Recording

- **On launch**: Creates a date folder (`YYYY-MM-DD`) under the data directory
- **On record start**: Creates an Excel file with Temperature, Pressure, Flow sheets
- **During recording**: Appends sensor data every second (auto-saves periodically)
- **On record stop**: Renames file to `HHMMSS_HHMMSS.xlsx` (start_end time)
- **Max duration**: 24 hours per recording session

## Communication

- Protocol: Modbus TCP
- Transport: Ethernet
- Default port: 502
- Polling: Configurable (default 1 second)
