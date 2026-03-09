"""
Firmware command definitions and simulation engine for Hamilton ML STAR.

This module models the IDL firmware protocol so that the HSL debugger can
validate, simulate, and report firmware commands instead of blindly
returning success for every device call.

Architecture
------------
- FirmwareParam: a single parameter in a firmware command (name, range, default)
- FirmwareCommand: one firmware command (code, SFCO id, params, response format)
- FirmwareCommandRegistry: holds all known commands, keyed by 2-letter code
- InstrumentState: mutable state of the simulated instrument (carriers,
  initialization, tip positions, etc.)
- FirmwareEngine: executes firmware commands against InstrumentState, validates
  parameters, builds response strings, and returns structured results.

The interpreter calls into FirmwareEngine via the DeviceSimulator wrapper,
which maps HSL step CLSIDs to firmware command sequences.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Optional


# ---------------------------------------------------------------------------
# Parameter and command definitions
# ---------------------------------------------------------------------------

class ParamType(Enum):
    """Firmware parameter value types."""
    INT = auto()
    FLOAT = auto()
    HEX = auto()
    BITFIELD = auto()
    STRING = auto()


@dataclass
class FirmwareParam:
    """One parameter in a firmware command."""
    name: str           # 2-letter mnemonic (e.g. "id", "cp", "cv")
    param_type: ParamType
    min_val: int = 0
    max_val: int = 9999
    default: int = 0
    description: str = ""
    width: int = 4      # number of digits/characters in protocol


@dataclass
class FirmwareCommand:
    """A single firmware command in the Hamilton IDL protocol."""
    code: str            # 2-letter command code (e.g. "II", "CL")
    sfco_id: str         # SFCO identifier (e.g. "SFCO.0005")
    category: str        # e.g. "Autoload Initialization"
    description: str
    command_point: int   # CP value from spec
    params: list[FirmwareParam] = field(default_factory=list)
    response_fields: list[str] = field(default_factory=list)
    notes: str = ""


class FirmwareCommandRegistry:
    """Registry of all known firmware commands."""

    def __init__(self):
        self.commands: dict[str, FirmwareCommand] = {}
        self._register_autoload_commands()

    def register(self, cmd: FirmwareCommand) -> None:
        self.commands[cmd.code] = cmd

    def get(self, code: str) -> Optional[FirmwareCommand]:
        return self.commands.get(code)

    def list_commands(self) -> list[str]:
        return sorted(self.commands.keys())

    # ------------------------------------------------------------------
    # Section 3.12 -- Autoload commands (from IDL Firmware.html)
    # ------------------------------------------------------------------

    def _register_autoload_commands(self) -> None:
        """Register all autoload firmware commands from IDL spec section 3.12."""

        # 3.12.1 Initialization

        self.register(FirmwareCommand(
            code="II", sfco_id="SFCO.0005",
            category="Autoload Initialization",
            description="Initialize Autoload",
            command_point=1,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
            ],
            response_fields=["id####", "er##/##"],
        ))

        self.register(FirmwareCommand(
            code="IV", sfco_id="SFCO.0251",
            category="Autoload Initialization",
            description="Move Autoload to Z save position",
            command_point=1,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
            ],
            response_fields=["id####", "er##/##"],
        ))

        # 3.12.2 Carrier handling

        self.register(FirmwareCommand(
            code="CI", sfco_id="SFCO.0013",
            category="Autoload Carrier Handling",
            description="Identify carrier (read barcode)",
            command_point=1,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
                FirmwareParam("cp", ParamType.INT, 1, 54, 1,
                              "Carrier position (slot number)"),
                FirmwareParam("bi", ParamType.INT, 0, 4700, 43,
                              "Carrier ID barcode position [0.1 mm]"),
                FirmwareParam("bw", ParamType.INT, 1, 999, 85,
                              "Carrier ID barcode reading window width [0.1mm]"),
                FirmwareParam("cv", ParamType.INT, 15, 1600, 1281,
                              "Carrier reading speed [0.1 mm/s]"),
            ],
            response_fields=["id####", "er##/##", "bb/nn'...'"],
            notes="Barcode data appended on success",
        ))

        self.register(FirmwareCommand(
            code="CT", sfco_id="SFCO.0075",
            category="Autoload Carrier Handling",
            description="Check presence of single carrier",
            command_point=1,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
                FirmwareParam("cp", ParamType.INT, 1, 54, 1,
                              "Carrier position (slot number)"),
            ],
            response_fields=["id####", "er##/##", "ct#"],
            notes="ct0 = not present, ct1 = present",
        ))

        self.register(FirmwareCommand(
            code="CA", sfco_id="SFCO.0015",
            category="Autoload Carrier Handling",
            description="Push out carrier to loading tray",
            command_point=1,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
            ],
            response_fields=["id####", "er##/##"],
            notes="Must be preceded by CI (identify)",
        ))

        self.register(FirmwareCommand(
            code="CR", sfco_id="SFCO.0016",
            category="Autoload Carrier Handling",
            description="Unload carrier",
            command_point=1,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
                FirmwareParam("cp", ParamType.INT, 1, 54, 1,
                              "Carrier position (slot number)"),
            ],
            response_fields=["id####", "er##/##"],
        ))

        self.register(FirmwareCommand(
            code="CL", sfco_id="SFCO.0014",
            category="Autoload Carrier Handling",
            description="Load carrier",
            command_point=1,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
                FirmwareParam("bd", ParamType.INT, 0, 1, 0,
                              "Barcode reading direction (0=vertical 1=horizontal)"),
                FirmwareParam("bp", ParamType.INT, 0, 4700, 100,
                              "Barcode reading position of first barcode [0.1mm]"),
                FirmwareParam("cn", ParamType.INT, 0, 32, 32,
                              "Number of containers in carrier"),
                FirmwareParam("co", ParamType.INT, 0, 4700, 150,
                              "Distance between containers [0.1 mm]"),
                FirmwareParam("cf", ParamType.INT, 1, 999, 100,
                              "Width of reading window [0.1 mm]"),
                FirmwareParam("ea", ParamType.INT, 0, 1, 0,
                              "Carrier read mode (0=fix grid 1=free definable)"),
                FirmwareParam("mr", ParamType.INT, 0, 1, 0,
                              "ROI Y-origin direction (0=positive 1=negative)"),
                FirmwareParam("cv", ParamType.INT, 15, 1600, 1281,
                              "Carrier reading speed [0.1 mm/s]"),
            ],
            response_fields=["id####", "er##/##", "vlnnnn...", "ci********",
                             "bb/nn'...'/nn'...'"],
            notes="Complex response includes container presence bitmap "
                  "and barcode data",
        ))

        self.register(FirmwareCommand(
            code="CP", sfco_id="SFCO.0017",
            category="Autoload Carrier Handling",
            description="Set loading indicators (LEDs)",
            command_point=1,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
                FirmwareParam("cl", ParamType.HEX, 0, 0x7FFFFFFFFFFFFFFF, 0,
                              "Bit pattern of LEDs (1=on 0=off)", width=14),
                FirmwareParam("cb", ParamType.HEX, 0, 0x7FFFFFFFFFFFFFFF, 0,
                              "Blink pattern of LEDs (1=blinking 0=steady)",
                              width=14),
            ],
            response_fields=["id####", "er##/##"],
        ))

        self.register(FirmwareCommand(
            code="CS", sfco_id="SFCO.0018",
            category="Autoload Carrier Handling",
            description="Check for presence of carriers on loading tray",
            command_point=1,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
            ],
            response_fields=["id####", "er##/##", "cd**************"],
            notes="Bit pattern: bit 54 (MSB) = position 55, "
                  "bit 0 (LSB) = position 1",
        ))

        self.register(FirmwareCommand(
            code="CB", sfco_id="SFCO.0072",
            category="Autoload Carrier Handling",
            description="Set barcode types and 2D reader features",
            command_point=1,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
                FirmwareParam("bt", ParamType.HEX, 0x00, 0xFF, 0x7F,
                              "Barcode types bitmask", width=2),
                FirmwareParam("mq", ParamType.HEX, 0x00, 0xFF, 0x00,
                              "2D code types bitmask (2D Autoload only)",
                              width=2),
                FirmwareParam("mb", ParamType.INT, 1, 10, 1,
                              "Max codes per image (2D Autoload only)"),
                FirmwareParam("mo", ParamType.INT, 0, 999, 0,
                              "Illumination settings (2D Autoload only)",
                              width=3),
            ],
            response_fields=["id####", "er##/##"],
        ))

        self.register(FirmwareCommand(
            code="DB", sfco_id="",
            category="Autoload Carrier Handling",
            description="Set code reading features for free definable carrier",
            command_point=1,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
                FirmwareParam("vn", ParamType.INT, 0, 32, 1,
                              "Labware position number (code index)"),
                FirmwareParam("bp", ParamType.INT, 0, 4700, 100,
                              "Code reading position [0.1mm]"),
                FirmwareParam("mr", ParamType.INT, 0, 1, 0,
                              "ROI Y-origin direction (0=positive 1=negative)"),
            ],
            response_fields=["id####", "er##/##"],
        ))

        self.register(FirmwareCommand(
            code="DR", sfco_id="",
            category="Autoload Carrier Handling",
            description="Reset free definable carrier settings",
            command_point=1,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
            ],
            response_fields=["id####", "er##/##"],
        ))

        self.register(FirmwareCommand(
            code="CW", sfco_id="SFCO.0140",
            category="Autoload Carrier Handling",
            description="Unload carrier finally",
            command_point=1,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
                FirmwareParam("cp", ParamType.INT, 1, 54, 1,
                              "Carrier position (slot number)"),
            ],
            response_fields=["id####", "er##/##"],
        ))

        self.register(FirmwareCommand(
            code="CU", sfco_id="SFCO.0146",
            category="Autoload Carrier Handling",
            description="Set carrier monitoring",
            command_point=1,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
                FirmwareParam("cu", ParamType.INT, 0, 1, 0,
                              "Monitoring (0=off 1=on)"),
            ],
            response_fields=["id####", "er##/##"],
        ))

        self.register(FirmwareCommand(
            code="CN", sfco_id="SFCO.0238",
            category="Autoload Carrier Handling",
            description="Take out carrier to identification position",
            command_point=1,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
                FirmwareParam("cp", ParamType.INT, 1, 54, 1,
                              "Carrier position (slot number)"),
            ],
            response_fields=["id####", "er##/##"],
        ))

        # 3.12.3 Autoload queries

        self.register(FirmwareCommand(
            code="RC", sfco_id="SFCO.0045",
            category="Autoload Query",
            description="Query presence of carrier on deck",
            command_point=0,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
            ],
            response_fields=["id####", "er##/##", "cd**************",
                             "ce**(26)"],
            notes="cd = 14-char compat bitmap, "
                  "ce = 26-char extended (104 slots)",
        ))

        self.register(FirmwareCommand(
            code="QA", sfco_id="SFCO.0200",
            category="Autoload Query",
            description="Request autoload slot position",
            command_point=0,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
            ],
            response_fields=["id####", "er##/##", "qa##"],
        ))

        self.register(FirmwareCommand(
            code="CQ", sfco_id="SFCO.0341",
            category="Autoload Query",
            description="Request autoload module type",
            command_point=0,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
            ],
            response_fields=["id####", "er##/##", "cq#"],
            notes="0=ML-Star with 1D Scanner, 1=XRP Lite, "
                  "2=ML-STAR with 2D Reader, 3..9=reserve",
        ))

        self.register(FirmwareCommand(
            code="VK", sfco_id="",
            category="Autoload Query",
            description="Request code data of individual labware position",
            command_point=1,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
                FirmwareParam("vn", ParamType.INT, 0, 32, 1,
                              "Labware position number"),
            ],
            response_fields=["id####", "er##/##", "vn##", "vm##",
                             "vlnnn", "vk..."],
            notes="2D Autoload only",
        ))

        self.register(FirmwareCommand(
            code="VL", sfco_id="",
            category="Autoload Query",
            description="Request code data length of all labware positions",
            command_point=0,
            params=[
                FirmwareParam("id", ParamType.INT, 0, 9999, 0,
                              "Identification number"),
            ],
            response_fields=["id####", "er##/##", "vlnnn nnn ..."],
            notes="2D Autoload only. Returns lengths from last CL command.",
        ))


# ---------------------------------------------------------------------------
# Instrument state
# ---------------------------------------------------------------------------

class CarrierState(Enum):
    """State of a carrier slot on the deck."""
    EMPTY = auto()
    PRESENT = auto()
    LOADED = auto()
    ON_TRAY = auto()
    IDENTIFIED = auto()


@dataclass
class CarrierSlot:
    """One carrier slot (position) on the autoload deck."""
    position: int          # 1-based slot number
    state: CarrierState = CarrierState.EMPTY
    barcode: str = ""
    carrier_type: str = ""
    containers: list[str] = field(default_factory=list)
    container_barcodes: list[str] = field(default_factory=list)
    led_on: bool = False
    led_blink: bool = False


@dataclass
class ChannelState:
    """State of a single pipetting channel."""
    channel_num: int       # 1-based channel number
    has_tip: bool = False
    tip_type: int = 0
    tip_volume_capacity: float = 0.0   # uL
    current_volume: float = 0.0        # uL of liquid currently held
    liquid_class: str = ""
    z_position: float = 0.0           # mm from top
    x_position: float = 0.0           # mm
    y_position: float = 0.0           # mm


@dataclass
class Head96State:
    """State of the CO-RE 96 head."""
    has_tips: bool = False
    tip_type: int = 0
    tip_volume_capacity: float = 0.0
    current_volume: float = 0.0
    liquid_class: str = ""
    z_position: float = 0.0


class InstrumentState:
    """Mutable state of the simulated Hamilton ML STAR instrument.

    Tracks: initialization status, carrier slots, channel states,
    96-head state, and other instrument subsystems.
    """

    def __init__(self, num_slots: int = 54, num_channels: int = 8):
        self.initialized: bool = False
        self.autoload_initialized: bool = False
        self.num_slots = num_slots
        self.num_channels = num_channels

        # Carrier deck
        self.carrier_slots: dict[int, CarrierSlot] = {
            i: CarrierSlot(position=i) for i in range(1, num_slots + 1)
        }

        # Pipetting channels
        self.channels: dict[int, ChannelState] = {
            i: ChannelState(channel_num=i) for i in range(1, num_channels + 1)
        }

        # CO-RE 96 head
        self.head96 = Head96State()

        # Carrier monitoring
        self.carrier_monitoring: bool = False

        # Autoload module type (0=1D, 2=2D)
        self.autoload_module_type: int = 0

        # Command sequence tracking
        self.command_history: list[FirmwareResult] = []

        # Error counters
        self.error_count: int = 0
        self.warning_count: int = 0


# ---------------------------------------------------------------------------
# Firmware execution results
# ---------------------------------------------------------------------------

@dataclass
class FirmwareResult:
    """Result of executing a firmware command."""
    command_code: str
    command_id: int
    success: bool
    error_code: int = 0
    trace_info: int = 0
    response_string: str = ""
    description: str = ""
    warnings: list[str] = field(default_factory=list)
    state_changes: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Firmware engine -- executes commands against instrument state
# ---------------------------------------------------------------------------

class FirmwareEngine:
    """Executes firmware commands against a simulated InstrumentState.

    Each command handler validates parameters, updates state, and returns
    a FirmwareResult with the simulated response string.
    """

    def __init__(self, state: Optional[InstrumentState] = None,
                 trace_fn: Optional[Any] = None):
        self.state = state or InstrumentState()
        self.registry = FirmwareCommandRegistry()
        self._trace = trace_fn or (lambda msg: None)

        # Map command codes to handler methods
        self._handlers: dict[str, Any] = {
            "II": self._handle_initialize_autoload,
            "IV": self._handle_move_z_save,
            "CI": self._handle_identify_carrier,
            "CT": self._handle_check_carrier,
            "CA": self._handle_push_out_carrier,
            "CR": self._handle_unload_carrier,
            "CL": self._handle_load_carrier,
            "CP": self._handle_set_leds,
            "CS": self._handle_check_tray_presence,
            "CB": self._handle_set_barcode_types,
            "DB": self._handle_set_code_reading,
            "DR": self._handle_reset_definable,
            "CW": self._handle_unload_finally,
            "CU": self._handle_set_monitoring,
            "CN": self._handle_take_out_to_id,
            "RC": self._handle_query_deck_presence,
            "QA": self._handle_query_slot_position,
            "CQ": self._handle_query_module_type,
            "VK": self._handle_request_code_data,
            "VL": self._handle_request_code_lengths,
        }

    def execute(self, code: str,
                params: Optional[dict[str, Any]] = None) -> FirmwareResult:
        """Execute a firmware command by its 2-letter code.

        Parameters
        ----------
        code : str
            Two-letter firmware command code (e.g. "II", "CL").
        params : dict, optional
            Parameter name -> value mapping. Missing params get defaults.

        Returns
        -------
        FirmwareResult
        """
        params = params or {}

        cmd_def = self.registry.get(code)
        if cmd_def is None:
            return FirmwareResult(
                command_code=code,
                command_id=params.get("id", 0),
                success=False,
                error_code=99,
                description=f"Unknown firmware command: {code}",
            )

        # Fill in defaults for missing parameters
        resolved = {}
        for p in cmd_def.params:
            if p.name in params:
                resolved[p.name] = params[p.name]
            else:
                resolved[p.name] = p.default

        # Validate parameter ranges
        validation_warnings = []
        for p in cmd_def.params:
            val = resolved.get(p.name, p.default)
            if p.param_type in (ParamType.INT, ParamType.FLOAT):
                try:
                    num_val = int(val) if p.param_type == ParamType.INT else float(val)
                    if num_val < p.min_val or num_val > p.max_val:
                        validation_warnings.append(
                            f"Parameter '{p.name}' value {num_val} "
                            f"out of range [{p.min_val}..{p.max_val}]"
                        )
                except (ValueError, TypeError):
                    validation_warnings.append(
                        f"Parameter '{p.name}' invalid value: {val}"
                    )

        # Dispatch to handler
        handler = self._handlers.get(code)
        if handler:
            result = handler(resolved, cmd_def)
        else:
            # No handler -- return generic success
            cmd_id = resolved.get("id", 0)
            result = FirmwareResult(
                command_code=code,
                command_id=cmd_id,
                success=True,
                response_string=f"{code}id{cmd_id:04d}er00/00",
                description=cmd_def.description,
            )

        result.warnings.extend(validation_warnings)

        # Log
        self._trace(
            f"[FW {code}] {cmd_def.description} -> "
            f"{'OK' if result.success else 'ERR'} "
            f"({result.response_string})"
        )
        for w in result.warnings:
            self._trace(f"[FW {code}] WARNING: {w}")

        # Record in history
        self.state.command_history.append(result)
        if not result.success:
            self.state.error_count += 1
        if result.warnings:
            self.state.warning_count += len(result.warnings)

        return result

    # ------------------------------------------------------------------
    # Response builder helper
    # ------------------------------------------------------------------

    @staticmethod
    def _ok_response(code: str, cmd_id: int,
                     extra: str = "") -> str:
        return f"{code}id{cmd_id:04d}er00/00{extra}"

    @staticmethod
    def _err_response(code: str, cmd_id: int,
                      err: int, trace: int = 0) -> str:
        return f"{code}id{cmd_id:04d}er{err:02d}/{trace:02d}"

    # ------------------------------------------------------------------
    # 3.12.1 Initialization handlers
    # ------------------------------------------------------------------

    def _handle_initialize_autoload(self, params: dict,
                                    cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        self.state.autoload_initialized = True
        return FirmwareResult(
            command_code="II",
            command_id=cmd_id,
            success=True,
            response_string=self._ok_response("II", cmd_id),
            description="Autoload initialized",
            state_changes=["autoload_initialized = True"],
        )

    def _handle_move_z_save(self, params: dict,
                            cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        if not self.state.autoload_initialized:
            return FirmwareResult(
                command_code="IV",
                command_id=cmd_id,
                success=False,
                error_code=2,
                response_string=self._err_response("IV", cmd_id, 2),
                description="Autoload not initialized",
                warnings=["Autoload must be initialized (II) before IV"],
            )
        return FirmwareResult(
            command_code="IV",
            command_id=cmd_id,
            success=True,
            response_string=self._ok_response("IV", cmd_id),
            description="Moved to Z save position",
        )

    # ------------------------------------------------------------------
    # 3.12.2 Carrier handling handlers
    # ------------------------------------------------------------------

    def _handle_identify_carrier(self, params: dict,
                                 cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        cp = params.get("cp", 1)
        slot = self.state.carrier_slots.get(cp)

        if slot is None:
            return FirmwareResult(
                command_code="CI", command_id=cmd_id, success=False,
                error_code=3,
                response_string=self._err_response("CI", cmd_id, 3),
                description=f"Invalid carrier position: {cp}",
            )

        # Simulate barcode read -- in real hardware this scans physically
        barcode = slot.barcode or f"SIM_CARRIER_{cp:02d}"
        slot.state = CarrierState.IDENTIFIED
        slot.barcode = barcode

        bb_data = f"bb/{len(barcode):02d}{barcode}"
        return FirmwareResult(
            command_code="CI", command_id=cmd_id, success=True,
            response_string=self._ok_response("CI", cmd_id, bb_data),
            description=f"Identified carrier at slot {cp}: {barcode}",
            state_changes=[f"slot[{cp}].state = IDENTIFIED",
                           f"slot[{cp}].barcode = {barcode}"],
        )

    def _handle_check_carrier(self, params: dict,
                              cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        cp = params.get("cp", 1)
        slot = self.state.carrier_slots.get(cp)

        if slot is None:
            return FirmwareResult(
                command_code="CT", command_id=cmd_id, success=False,
                error_code=3,
                response_string=self._err_response("CT", cmd_id, 3),
                description=f"Invalid carrier position: {cp}",
            )

        present = 1 if slot.state != CarrierState.EMPTY else 0
        return FirmwareResult(
            command_code="CT", command_id=cmd_id, success=True,
            response_string=self._ok_response("CT", cmd_id, f"ct{present}"),
            description=f"Carrier at slot {cp}: "
                        f"{'present' if present else 'not present'}",
        )

    def _handle_push_out_carrier(self, params: dict,
                                 cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        # CA pushes whatever was identified back to the tray
        # Find the last identified carrier
        changed = []
        for pos, slot in self.state.carrier_slots.items():
            if slot.state == CarrierState.IDENTIFIED:
                slot.state = CarrierState.ON_TRAY
                changed.append(f"slot[{pos}].state = ON_TRAY")

        return FirmwareResult(
            command_code="CA", command_id=cmd_id, success=True,
            response_string=self._ok_response("CA", cmd_id),
            description="Pushed out carrier to loading tray",
            state_changes=changed,
        )

    def _handle_unload_carrier(self, params: dict,
                               cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        cp = params.get("cp", 1)
        slot = self.state.carrier_slots.get(cp)

        if slot is None:
            return FirmwareResult(
                command_code="CR", command_id=cmd_id, success=False,
                error_code=3,
                response_string=self._err_response("CR", cmd_id, 3),
                description=f"Invalid carrier position: {cp}",
            )

        if slot.state == CarrierState.EMPTY:
            return FirmwareResult(
                command_code="CR", command_id=cmd_id, success=False,
                error_code=5,
                response_string=self._err_response("CR", cmd_id, 5),
                description=f"No carrier at slot {cp} to unload",
                warnings=[f"Attempted to unload empty slot {cp}"],
            )

        slot.state = CarrierState.EMPTY
        return FirmwareResult(
            command_code="CR", command_id=cmd_id, success=True,
            response_string=self._ok_response("CR", cmd_id),
            description=f"Unloaded carrier from slot {cp}",
            state_changes=[f"slot[{cp}].state = EMPTY"],
        )

    def _handle_load_carrier(self, params: dict,
                             cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        # CL loads from tray -- the tray is implicit, loading to the
        # slot determined by the autoload mechanism
        cn = params.get("cn", 32)  # number of containers

        # Find the first available slot or use the tray carrier
        target_slot = None
        for pos, slot in self.state.carrier_slots.items():
            if slot.state == CarrierState.ON_TRAY:
                target_slot = slot
                break

        if target_slot is None:
            # Simulate loading into slot 1 if nothing is on tray
            target_slot = self.state.carrier_slots[1]

        target_slot.state = CarrierState.LOADED
        target_slot.containers = [f"C{i+1}" for i in range(cn)]

        # Build simulated container presence bitmap (all present)
        ci_val = (1 << cn) - 1 if cn <= 32 else 0xFFFFFFFF
        ci_hex = f"{ci_val:08X}"

        # Build simulated barcode data
        bb_parts = []
        for i in range(cn):
            bc = target_slot.container_barcodes[i] if i < len(
                target_slot.container_barcodes) else ""
            if bc:
                bb_parts.append(f"{len(bc):02d}{bc}")
            else:
                bb_parts.append("00")

        # Simplified response
        vl_data = " ".join(f"{len(bc):04d}" for bc in
                           (target_slot.container_barcodes[:cn]
                            if target_slot.container_barcodes else [""]*cn))

        extra = f"ci{ci_hex}"
        return FirmwareResult(
            command_code="CL", command_id=cmd_id, success=True,
            response_string=self._ok_response("CL", cmd_id, extra),
            description=(f"Loaded carrier to slot {target_slot.position} "
                         f"with {cn} containers"),
            state_changes=[
                f"slot[{target_slot.position}].state = LOADED",
                f"slot[{target_slot.position}].containers = {cn} items",
            ],
        )

    def _handle_set_leds(self, params: dict,
                         cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        cl_val = params.get("cl", 0)
        cb_val = params.get("cb", 0)

        # Update LED states on slots
        for pos in range(1, self.state.num_slots + 1):
            bit = pos - 1
            slot = self.state.carrier_slots[pos]
            slot.led_on = bool((cl_val >> bit) & 1)
            slot.led_blink = bool((cb_val >> bit) & 1)

        return FirmwareResult(
            command_code="CP", command_id=cmd_id, success=True,
            response_string=self._ok_response("CP", cmd_id),
            description="Set loading indicators",
        )

    def _handle_check_tray_presence(self, params: dict,
                                     cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        # Build bit pattern of carriers on tray
        bitmap = 0
        for pos in range(1, self.state.num_slots + 1):
            if self.state.carrier_slots[pos].state == CarrierState.ON_TRAY:
                bitmap |= (1 << (pos - 1))
        cd_hex = f"{bitmap:014X}"

        return FirmwareResult(
            command_code="CS", command_id=cmd_id, success=True,
            response_string=self._ok_response("CS", cmd_id, f"cd{cd_hex}"),
            description="Checked tray presence",
        )

    def _handle_set_barcode_types(self, params: dict,
                                  cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        return FirmwareResult(
            command_code="CB", command_id=cmd_id, success=True,
            response_string=self._ok_response("CB", cmd_id),
            description="Set barcode reader types",
        )

    def _handle_set_code_reading(self, params: dict,
                                 cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        return FirmwareResult(
            command_code="DB", command_id=cmd_id, success=True,
            response_string=self._ok_response("DB", cmd_id),
            description="Set code reading features for free definable carrier",
        )

    def _handle_reset_definable(self, params: dict,
                                cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        return FirmwareResult(
            command_code="DR", command_id=cmd_id, success=True,
            response_string=self._ok_response("DR", cmd_id),
            description="Reset free definable carrier settings",
        )

    def _handle_unload_finally(self, params: dict,
                               cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        cp = params.get("cp", 1)
        slot = self.state.carrier_slots.get(cp)
        if slot:
            slot.state = CarrierState.EMPTY
            slot.barcode = ""
            slot.containers = []
            slot.container_barcodes = []
        return FirmwareResult(
            command_code="CW", command_id=cmd_id, success=True,
            response_string=self._ok_response("CW", cmd_id),
            description=f"Unloaded carrier from slot {cp} (final)",
            state_changes=[f"slot[{cp}] cleared"],
        )

    def _handle_set_monitoring(self, params: dict,
                               cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        cu = params.get("cu", 0)
        self.state.carrier_monitoring = bool(cu)
        return FirmwareResult(
            command_code="CU", command_id=cmd_id, success=True,
            response_string=self._ok_response("CU", cmd_id),
            description=f"Carrier monitoring {'on' if cu else 'off'}",
            state_changes=[f"carrier_monitoring = {bool(cu)}"],
        )

    def _handle_take_out_to_id(self, params: dict,
                               cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        cp = params.get("cp", 1)
        slot = self.state.carrier_slots.get(cp)
        if slot and slot.state != CarrierState.EMPTY:
            slot.state = CarrierState.IDENTIFIED
        return FirmwareResult(
            command_code="CN", command_id=cmd_id, success=True,
            response_string=self._ok_response("CN", cmd_id),
            description=f"Took out carrier from slot {cp} to ID position",
        )

    # ------------------------------------------------------------------
    # 3.12.3 Query handlers
    # ------------------------------------------------------------------

    def _handle_query_deck_presence(self, params: dict,
                                    cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        bitmap = 0
        for pos in range(1, self.state.num_slots + 1):
            if self.state.carrier_slots[pos].state not in (
                    CarrierState.EMPTY, CarrierState.ON_TRAY):
                bitmap |= (1 << (pos - 1))
        cd_hex = f"{bitmap:014X}"
        # Extended 26-char carrier presence (104 slots)
        ce_hex = f"{bitmap:026X}"

        return FirmwareResult(
            command_code="RC", command_id=cmd_id, success=True,
            response_string=self._ok_response(
                "RC", cmd_id, f"cd{cd_hex}ce{ce_hex}"),
            description="Queried carrier deck presence",
        )

    def _handle_query_slot_position(self, params: dict,
                                    cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        # Return current autoload slot position (simulated)
        qa = 1  # default slot position
        return FirmwareResult(
            command_code="QA", command_id=cmd_id, success=True,
            response_string=self._ok_response("QA", cmd_id, f"qa{qa:02d}"),
            description=f"Autoload slot position: {qa}",
        )

    def _handle_query_module_type(self, params: dict,
                                  cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        cq = self.state.autoload_module_type
        return FirmwareResult(
            command_code="CQ", command_id=cmd_id, success=True,
            response_string=self._ok_response("CQ", cmd_id, f"cq{cq}"),
            description=f"Autoload module type: {cq}",
        )

    def _handle_request_code_data(self, params: dict,
                                  cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        vn = params.get("vn", 1)
        # Return simulated barcode data for the position
        code = f"SIM_BC_{vn:02d}"
        vl = len(code)
        return FirmwareResult(
            command_code="VK", command_id=cmd_id, success=True,
            response_string=self._ok_response(
                "VK", cmd_id, f"vn{vn:02d}vm01vl{vl:03d}vk{code}"),
            description=f"Code data for position {vn}: {code}",
        )

    def _handle_request_code_lengths(self, params: dict,
                                     cmd_def: FirmwareCommand) -> FirmwareResult:
        cmd_id = params["id"]
        # Return simulated code lengths (all zeros -- no real data)
        lengths = " ".join("000" for _ in range(32))
        return FirmwareResult(
            command_code="VL", command_id=cmd_id, success=True,
            response_string=self._ok_response("VL", cmd_id, f"vl{lengths}"),
            description="Code data lengths for all labware positions",
        )


# ---------------------------------------------------------------------------
# Device Simulator -- maps HSL step CLSIDs to firmware commands
# ---------------------------------------------------------------------------

# CLSID -> (step_type_name, list_of_firmware_commands)
CLSID_MAP: dict[str, tuple[str, list[str]]] = {
    "1C0C0CB0_7C87_11D3_AD83_0004ACB1DCB2": ("Initialize", ["II"]),
    "541143F5_7FA2_11D3_AD85_0004ACB1DCB2": ("Aspirate", []),
    "541143F8_7FA2_11D3_AD85_0004ACB1DCB2": ("Dispense", []),
    "541143FA_7FA2_11D3_AD85_0004ACB1DCB2": ("TipPickUp", []),
    "541143FC_7FA2_11D3_AD85_0004ACB1DCB2": ("TipEject", []),
    "54114400_7FA2_11D3_AD85_0004ACB1DCB2": ("UnloadCarrier", ["CR"]),
    "54114402_7FA2_11D3_AD85_0004ACB1DCB2": ("LoadCarrier", ["CL"]),
    "827392A0_B7E8_4472_9ED3_B45B71B5D27A": ("Head96Aspirate", []),
    "A48573A5_62ED_4951_9EF9_03207EFE34FB": ("Head96Dispense", []),
    "BD0D210B_0816_4C86_A903_D6B2DF73F78B": ("Head96TipPickUp", []),
    "2880E77A_3D6D_40FE_AF57_1BD1FE13960C": ("Head96TipEject", []),
    "EA251BFB_66DE_48D1_83E5_6884B4DD8D11": ("MoveAutoLoad", ["IV"]),
}


class DeviceSimulator:
    """High-level simulator that maps HSL device step calls to firmware
    command sequences.

    The interpreter calls ``execute_step()`` whenever it sees a device
    method call like ``ML_STAR._<CLSID>("stepGuid")``.
    """

    def __init__(self, trace_fn: Optional[Any] = None):
        self.state = InstrumentState()
        self.engine = FirmwareEngine(state=self.state, trace_fn=trace_fn)
        self._trace = trace_fn or (lambda msg: None)

    def execute_step(self, method_name: str,
                     step_guid: str,
                     step_params: Optional[dict] = None) -> FirmwareResult:
        """Execute an HSL device step.

        Parameters
        ----------
        method_name : str
            The method name from the MethodCall node, e.g.
            ``"_541143F5_7FA2_11D3_AD85_0004ACB1DCB2"``
        step_guid : str
            The step instance GUID (first argument to the call).
        step_params : dict, optional
            Parameters decoded from the .stp file (future use).

        Returns
        -------
        FirmwareResult
        """
        # Extract CLSID from method name (strip leading underscore)
        clsid = method_name.lstrip("_")

        step_info = CLSID_MAP.get(clsid)
        if step_info is None:
            self._trace(
                f"[SIM] Unknown device step CLSID: {clsid} "
                f"(guid={step_guid})")
            # Return generic success for unknown steps
            return FirmwareResult(
                command_code="??",
                command_id=0,
                success=True,
                description=f"Unknown step CLSID: {clsid} "
                            "(simulated as success)",
            )

        step_type, fw_commands = step_info
        self._trace(
            f"[SIM] Device step: {step_type} "
            f"(CLSID={clsid}, guid={step_guid})")

        # The Initialize step sets the global initialized flag
        if step_type == "Initialize":
            self.state.initialized = True

        # Check that instrument is initialized before non-Initialize steps
        if step_type != "Initialize" and not self.state.initialized:
            self._trace(
                f"[SIM] ERROR: {step_type} called before Initialize!")
            return FirmwareResult(
                command_code=step_type[:2].upper(),
                command_id=0,
                success=False,
                error_code=1,
                description=(f"{step_type} failed: instrument not "
                             "initialized (call Initialize first)"),
                warnings=["Device must be initialized before any "
                          "other device commands"],
            )

        if not fw_commands:
            # Step type known but no firmware commands mapped yet
            # (e.g., Aspirate, Dispense -- firmware spec not yet available)
            self._trace(
                f"[SIM] {step_type}: no firmware commands mapped "
                "(stub -- returning success)")
            return FirmwareResult(
                command_code=step_type[:2].upper(),
                command_id=0,
                success=True,
                description=f"{step_type} (no firmware mapping -- stub)",
            )

        # Execute the firmware command sequence
        last_result = None
        for fw_code in fw_commands:
            fw_params = step_params or {}
            last_result = self.engine.execute(fw_code, fw_params)
            if not last_result.success:
                self._trace(
                    f"[SIM] {step_type}: firmware command {fw_code} "
                    f"failed: {last_result.description}")
                return last_result

        return last_result or FirmwareResult(
            command_code="OK",
            command_id=0,
            success=True,
            description=f"{step_type} completed (no commands)",
        )

    def get_state_summary(self) -> str:
        """Return a human-readable summary of instrument state."""
        lines = []
        lines.append("=== Instrument State ===")
        lines.append(f"Initialized: {self.state.initialized}")
        lines.append(f"Autoload initialized: {self.state.autoload_initialized}")
        lines.append(f"Carrier monitoring: {self.state.carrier_monitoring}")
        lines.append(f"Commands executed: {len(self.state.command_history)}")
        lines.append(f"Errors: {self.state.error_count}")
        lines.append(f"Warnings: {self.state.warning_count}")

        # Show occupied carrier slots
        occupied = []
        for pos, slot in self.state.carrier_slots.items():
            if slot.state != CarrierState.EMPTY:
                occupied.append(f"  Slot {pos}: {slot.state.name} "
                                f"barcode={slot.barcode or '(none)'}")
        if occupied:
            lines.append("Carrier slots:")
            lines.extend(occupied)
        else:
            lines.append("Carrier slots: all empty")

        # Show channel states
        channels_with_tips = [
            ch for ch in self.state.channels.values() if ch.has_tip
        ]
        if channels_with_tips:
            lines.append("Channels with tips:")
            for ch in channels_with_tips:
                lines.append(
                    f"  Ch{ch.channel_num}: tip_type={ch.tip_type} "
                    f"vol={ch.current_volume}/{ch.tip_volume_capacity} uL")
        else:
            lines.append("Channels: no tips loaded")

        # 96-head
        if self.state.head96.has_tips:
            lines.append(
                f"96-Head: tips loaded, tip_type={self.state.head96.tip_type} "
                f"vol={self.state.head96.current_volume}/"
                f"{self.state.head96.tip_volume_capacity} uL")
        else:
            lines.append("96-Head: no tips")

        return "\n".join(lines)

    def get_command_log(self) -> list[str]:
        """Return a list of all executed commands with results."""
        lines = []
        for r in self.state.command_history:
            status = "OK" if r.success else f"ERR({r.error_code})"
            lines.append(f"[{r.command_code}] {status} - {r.description}")
            for w in r.warnings:
                lines.append(f"  WARNING: {w}")
        return lines
