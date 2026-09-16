"""Costanti e catalogo registri per l'integrazione Sabiana Fancoil.

Tutti gli indirizzi sono verificati contro:
"Protocollo MODBUS - Sabiana MB EXT rev.12", sezione
"Dati MODBUS - Cassette e Fancoil" (pagg. 6-12).

Gli indirizzi sono espressi in decimale, pronti per essere passati a
pymodbus (holding register, function code 0x03 in lettura / 0x06 in
scrittura). La conversione dall'esadecimale del PDF è: decimale = 4096 + hex.

NOTA IMPORTANTE (da verificare sul campo): il registro 1000 (indirizzo
decimale 4096) restituisce il modello del controllore:
    5000 = Cassette        5002 = FanCoil
    5001 = Cassette ECM    5003 = FanCoil ECM
Le unità "ECM" hanno un motore ventola a tensione variabile e in quel
caso i registri di stato ventilazione (1019/101A/101B) NON sono
significativi durante il funzionamento in automatico (lo dice
esplicitamente il protocollo). Se anche una sola delle 9 unità di
Paolo risultasse ECM, il select "velocità ventola" andrebbe rivisto
per quella unità.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


DOMAIN = "sabiana_fancoil"

# Parametri seriali imposti dal protocollo stesso (non modificabili
# lato utente: "L'interfaccia seriale deve essere così configurata:
# 9600 bit/sec, 8 bit, No parità, 1 bit di stop").
SERIAL_BAUDRATE = 9600
SERIAL_BYTESIZE = 8
SERIAL_PARITY = "N"
SERIAL_STOPBITS = 1

CONF_PORT = "port"
CONF_SLAVE = "slave"
CONF_ROOM_NAME = "room_name"

SUBENTRY_TYPE_FANCOIL = "fancoil"

# Ritardo minimo (secondi) da rispettare tra due transazioni Modbus
# consecutive sullo stesso bus RS485 (era "message_wait_milliseconds:
# 50" nel file YAML originale).
INTER_MESSAGE_DELAY = 0.05


class DataType(StrEnum):
    INT16 = "int16"
    UINT16 = "uint16"


@dataclass(frozen=True, kw_only=True)
class SensorDef:
    """Un sensore in sola lettura, uguale per ogni fancoil configurato."""

    key: str
    name: str
    address: int  # holding register, decimale
    data_type: DataType = DataType.INT16
    scale: float = 1
    precision: int | None = None
    unit: str | None = None
    entity_category: str | None = None  # "diagnostic" oppure None
    scan_interval: int = 60


@dataclass(frozen=True, kw_only=True)
class SwitchDef:
    """Uno switch scrivibile, con verifica opzionale dello stato reale."""

    key: str
    name: str
    write_address: int
    verify_address: int | None = None
    command_on: int = 1
    command_off: int = 0
    entity_category: str | None = None


@dataclass(frozen=True, kw_only=True)
class FanSpeedDef:
    """Selettore velocità ventola: 4 registri di stato + 1 di comando."""

    command_address: int  # 0x1059 - scrittura 0/1/2/3
    auto_state_address: int  # 0x1017
    min_state_address: int  # 0x1019
    med_state_address: int  # 0x101A
    max_state_address: int  # 0x101B
    options: tuple[str, ...] = ("Automatico", "Minimo", "Medio", "Massimo")


@dataclass(frozen=True, kw_only=True)
class ClimateDef:
    """Registri per l'entità climate unificata di ogni fancoil."""

    current_temp_address: int  # 0x1002 - Sonda T1
    season_state_address: int  # 0x1013 - Stato Stagione impostata (0=Estate,1=Inverno)
    setpoint_estate_address: int  # 0x102D
    setpoint_inverno_address: int  # 0x102E
    power_write_address: int  # 0x1057 - Comando ON-OFF
    power_state_address: int  # 0x100F - Stato Macchina
    mode_write_address: int  # 0x1058 - Comando modalità (0=Estate,1=Inverno,2=SoloVent,3=Auto)
    fan_speed: FanSpeedDef
    min_temp: float = 10.0
    max_temp: float = 30.0
    temp_step: float = 0.5


# --- Catalogo sensori diagnostici / di lettura -----------------------------
SENSORS: tuple[SensorDef, ...] = (
    SensorDef(
        key="model",
        name="Modello Hardware",
        address=4096,  # 0x1000
        entity_category="diagnostic",
        scan_interval=86400,  # dato fisso, non cambia mai
    ),
    SensorDef(
        key="temp_t3",
        name="Sonda T3",
        address=4100,  # 0x1004
        unit="°C",
        scale=0.1,
        precision=1,
        scan_interval=30,
    ),
    SensorDef(
        key="isteresi",
        name="Isteresi sui Set",
        address=4152,  # 0x1038
        unit="°C",
        scale=0.1,
        precision=1,
        entity_category="diagnostic",
        scan_interval=600,
    ),
)

# --- Catalogo switch --------------------------------------------------------
SWITCHES: tuple[SwitchDef, ...] = (
    SwitchDef(
        key="power",
        name="Accensione",
        write_address=4183,  # 0x1057
        verify_address=4111,  # 0x100F - Stato Macchina
    ),
    SwitchDef(
        key="sonda_esterna_abilitata",
        name="Sonda Esterna via MB",
        write_address=4207,  # 0x106F
        verify_address=4207,
        entity_category="diagnostic",
    ),
)

# --- Selettore velocità ventola (uguale per tutti) --------------------------
FAN_SPEED = FanSpeedDef(
    command_address=4185,  # 0x1059
    auto_state_address=4119,  # 0x1017
    min_state_address=4121,  # 0x1019
    med_state_address=4122,  # 0x101A
    max_state_address=4123,  # 0x101B
)

# --- Climate -----------------------------------------------------------------
CLIMATE = ClimateDef(
    current_temp_address=4098,  # 0x1002 - Sonda T1
    season_state_address=4115,  # 0x1013 - Stato Stagione impostata
    setpoint_estate_address=4141,  # 0x102D
    setpoint_inverno_address=4142,  # 0x102E
    power_write_address=4183,  # 0x1057
    power_state_address=4111,  # 0x100F
    mode_write_address=4184,  # 0x1058
    fan_speed=FAN_SPEED,
)
