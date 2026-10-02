# Sabiana Modbus Home Assistant Integration

This custom integration allows you to control Sabiana FanCoils via the Modbus protocol in Home Assistant.

## Features

- Control your fancoils (ON/OFF, temperature setpoint, fan speed, mode).
- Monitor diagnostic sensors (hardware model, temperature probes, hysteresis).
- **New! External Temperature Sensor Support**: You can now link an external temperature sensor to the Fancoil via the Modbus register 4208.

## Installation

Add this repository to your HACS custom repositories, then restart Home Assistant and add the Sabiana integration.

## Configuration

During configuration, add your fancoils by providing:
- The slave address (1-60) configured on the dip-switches.
- A name for the room.
- (Optional) An entity ID for an external temperature sensor to synchronize with the machine.
