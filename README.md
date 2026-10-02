# Sabiana Fancoil Home Assistant Integration (Modbus RTU / RS485)

Custom Home Assistant integration for Sabiana Fancoils (Cassette and Fancoil units using MB EXT protocol via RS485 Modbus RTU).

## Architecture

- **Config Entry (Hub)**: Represents an RS485 serial bus connected via a serial adapter (e.g., `/dev/ttyUSB0`). Manages a single shared `AsyncModbusSerialClient` instance and an `asyncio.Lock`.
- **Subentries (Fancoils)**: Each fancoil connected to the bus is a configuration subentry defined by its slave ID and room name. Each subentry corresponds to a Home Assistant device and a dedicated `SabianaCoordinator`.
- **Bus Serialization**: All read/write operations across all fancoils share the same bus lock and respect inter-message delays (`INTER_MESSAGE_DELAY`), preventing half-duplex RS485 collisions.

---

## Handled Edge Cases & Robustness

### 1. Serial Port Leak Prevention
- **Issue**: Previously, if setup failed halfway (e.g., communication timeout during the initial refresh), `runtime_data` wasn't set and the serial port remained open and locked by Python ("Connection already in use" / `Resource busy`).
- **Solution**: Setup is wrapped in a `try...except` block that guarantees the serial client is properly closed if any exception occurs during initialization. Unloading also safely closes the client.

### 2. Automatic Reconnection (Auto-Reconnect)
- **Issue**: Transient disconnections or hardware resets of the USB-RS485 adapter would permanently break communication until Home Assistant was restarted or the integration was manually reloaded.
- **Solution**: Before every read or write operation, the coordinator checks `client.connected`. If the connection is dropped, it automatically attempts to reconnect (`client.connect()`) before proceeding.

### 3. Smart Climate Season Handling
- **Issue**: Standard thermostat integrations usually bind to a static temperature setpoint register.
- **Solution**: The `SabianaClimate` entity dynamically checks the active season register (`0x1013`) on every read/write operation, automatically mapping the target temperature to either the Summer setpoint (`0x102D`) or Winter setpoint (`0x102E`).

---

## Entities Provided

- **Climate**: Unified thermostat supporting Heat, Cool, Off modes, fan speed control, and dynamic temperature setpoints.
- **Sensor**: Hardware model, T3 probe temperature, and hysteresis (with diagnostic entity categories and custom scan intervals).
- **Switch**: Power toggle and external probe enablement via Modbus registers.
- **Select**: Fan speed selector (`auto`, `min`, `med`, `max`) and season selector (`cool`, `heat`).
