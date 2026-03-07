"""
COM Object Simulation for HSL Debugger
=======================================
Pure-Python implementations of COM objects that HSL methods call via
object.CreateObject(). Each registered ProgID maps to a Python class
that implements the same methods.

SIMULATION ONLY - These are NOT real COM objects. They replicate the
behaviour of registered COM servers using pure Python + sqlite3.
"""

import os
import re
import sqlite3
import json
from datetime import datetime
from typing import Any, Optional


# ============================================================================
# COM Object Registry
# ============================================================================

# Maps ProgID -> Python class
_COM_REGISTRY: dict[str, type] = {}


def register_com_class(prog_id: str):
    """Decorator to register a Python class as a COM object simulation."""
    def decorator(cls):
        _COM_REGISTRY[prog_id.lower()] = cls
        return cls
    return decorator


def create_com_object(prog_id: str) -> Optional[Any]:
    """Create a simulated COM object by ProgID. Returns None if unknown."""
    cls = _COM_REGISTRY.get(prog_id.lower())
    if cls:
        return cls()
    return None


# ============================================================================
# BarcodedTipTracking.Engine
# ============================================================================

@register_com_class("BarcodedTipTracking.Engine")
class BarcodedTipTrackingEngine:
    """
    Pure-Python simulation of the BarcodedTipTrackingCOM C# COM object.
    Uses sqlite3 for database storage, replicating the exact schema and
    query logic from TipTrackingEngine.cs and DatabaseManager.cs.
    """

    DATABASE_DIR = r"C:\Program Files (x86)\Hamilton\Databases"
    DATABASE_FILE = "tip_barcoded_sequence_tracking.sqlite"

    def __init__(self):
        self._conn: Optional[sqlite3.Connection] = None
        self._db_path = os.path.join(self.DATABASE_DIR, self.DATABASE_FILE)

    # ----------------------------------------------------------------
    #  Lifecycle
    # ----------------------------------------------------------------

    def Initialize(self) -> None:
        """Ensure the database directory and file exist; create tables if needed."""
        if not os.path.exists(self.DATABASE_DIR):
            os.makedirs(self.DATABASE_DIR, exist_ok=True)

        self._conn = sqlite3.connect(self._db_path)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._apply_schema()

    def _apply_schema(self) -> None:
        ddl = """
CREATE TABLE IF NOT EXISTS tip_usage (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    barcode         TEXT    NOT NULL,
    used_positions  TEXT    NOT NULL,
    tip_type        TEXT,
    method_name     TEXT,
    method_guid     TEXT,
    timestamp       TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_tip_usage_barcode ON tip_usage(barcode);
CREATE INDEX IF NOT EXISTS idx_tip_usage_tip_type ON tip_usage(tip_type);
"""
        self._conn.executescript(ddl)
        # Migrate: check for method_guid column
        cursor = self._conn.execute("PRAGMA table_info(tip_usage)")
        cols = [row[1] for row in cursor.fetchall()]
        if "method_guid" not in cols:
            self._conn.execute("ALTER TABLE tip_usage ADD COLUMN method_guid TEXT")
            self._conn.commit()

    def _ensure_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self.Initialize()
        return self._conn

    # ----------------------------------------------------------------
    #  Core operations
    # ----------------------------------------------------------------

    def LogUsedPositions(self, barcode: str, positions_csv: str,
                         tip_type: str, method_name: str, method_guid: str) -> str:
        conn = self._ensure_conn()
        positions = self._parse_positions(positions_csv)
        sorted_pos = self._sort_positions(positions)
        positions_str = ",".join(sorted_pos)

        cursor = conn.execute(
            """INSERT INTO tip_usage (barcode, used_positions, tip_type, method_name, method_guid)
               VALUES (?, ?, ?, ?, ?)""",
            (barcode.strip(), positions_str, tip_type or "", method_name or "", method_guid or "")
        )
        conn.commit()
        return str(cursor.lastrowid)

    def GetUsedPositions(self, barcode: str) -> str:
        if not barcode or not barcode.strip():
            return ""
        conn = self._ensure_conn()
        cursor = conn.execute(
            "SELECT used_positions FROM tip_usage WHERE barcode = ?",
            (barcode.strip(),)
        )
        all_positions = set()
        for row in cursor.fetchall():
            for p in self._parse_positions(row[0]):
                all_positions.add(p)
        return ",".join(self._sort_positions(all_positions))

    def GetAvailablePositions(self, barcode: str, all_positions_csv: str) -> str:
        if not all_positions_csv or not all_positions_csv.strip():
            return ""
        all_pos = self._parse_positions(all_positions_csv)
        used_str = self.GetUsedPositions(barcode)
        used = set(p.upper() for p in self._parse_positions(used_str))
        available = [p for p in all_pos if p.upper() not in used]
        return ",".join(self._sort_positions(available))

    # ----------------------------------------------------------------
    #  Reporting / dashboard queries
    # ----------------------------------------------------------------

    def GetAllBarcodes(self) -> str:
        conn = self._ensure_conn()
        cursor = conn.execute("SELECT DISTINCT barcode FROM tip_usage ORDER BY barcode")
        barcodes = [self._json_escape(row[0]) for row in cursor.fetchall()]
        return "[" + ",".join(barcodes) + "]"

    def GetUsageStats(self) -> str:
        conn = self._ensure_conn()
        cursor = conn.execute("""
            SELECT tip_type,
                   COUNT(DISTINCT barcode) AS barcode_count,
                   SUM(LENGTH(used_positions) - LENGTH(REPLACE(used_positions, ',', '')) + 1) AS total_positions
            FROM tip_usage
            GROUP BY tip_type
            ORDER BY tip_type
        """)
        items = []
        for row in cursor.fetchall():
            items.append(
                '{' +
                '"tipType":{},"barcodeCount":{},"totalPositions":{}'.format(
                    self._json_escape(row[0] or ""),
                    row[1],
                    row[2]
                ) +
                '}'
            )
        return "[" + ",".join(items) + "]"

    def GetUsageHistory(self, barcode: str) -> str:
        conn = self._ensure_conn()
        cursor = conn.execute(
            """SELECT id, barcode, used_positions, tip_type, method_name, method_guid, timestamp
               FROM tip_usage
               WHERE barcode = ?
               ORDER BY timestamp ASC""",
            ((barcode or "").strip(),)
        )
        items = []
        for row in cursor.fetchall():
            items.append(self._record_to_json(row))
        return "[" + ",".join(items) + "]"

    def ClearBarcode(self, barcode: str) -> None:
        if not barcode or not barcode.strip():
            return
        conn = self._ensure_conn()
        conn.execute("DELETE FROM tip_usage WHERE barcode = ?", (barcode.strip(),))
        conn.commit()

    def GetAllRecords(self) -> str:
        conn = self._ensure_conn()
        cursor = conn.execute(
            """SELECT id, barcode, used_positions, tip_type, method_name, method_guid, timestamp
               FROM tip_usage
               ORDER BY timestamp DESC"""
        )
        items = []
        for row in cursor.fetchall():
            items.append(self._record_to_json(row))
        return "[" + ",".join(items) + "]"

    def GetBarcodeSummaries(self) -> str:
        conn = self._ensure_conn()
        cursor = conn.execute("""
            SELECT barcode,
                   tip_type,
                   MIN(timestamp) AS first_seen,
                   MAX(timestamp) AS last_seen,
                   GROUP_CONCAT(used_positions) AS all_positions
            FROM tip_usage
            GROUP BY barcode
            ORDER BY MAX(timestamp) DESC
        """)
        items = []
        for row in cursor.fetchall():
            all_pos_raw = row[4] or ""
            unique = set()
            for p in self._parse_positions(all_pos_raw):
                unique.add(p)
            sorted_pos = self._sort_positions(unique)
            items.append(
                '{' +
                '"barcode":{},"tipType":{},"totalUsed":{},"firstSeen":{},"lastSeen":{},"usedPositions":{}'.format(
                    self._json_escape(row[0] or ""),
                    self._json_escape(row[1] or ""),
                    len(sorted_pos),
                    self._json_escape(row[2] or ""),
                    self._json_escape(row[3] or ""),
                    self._json_escape(",".join(sorted_pos))
                ) +
                '}'
            )
        return "[" + ",".join(items) + "]"

    # ----------------------------------------------------------------
    #  IDL Picture snapshot
    # ----------------------------------------------------------------

    def TakeIdlPicture(self, barcode: str, run_id: str) -> str:
        if not barcode or not barcode.strip():
            return ""

        safe_barcode = self._sanitize_filename(barcode)
        safe_run_id = self._sanitize_filename(run_id) if run_id and run_id.strip() else "no_run"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        picture_dir = os.path.join(
            r"C:\Program Files (x86)\Hamilton\LogFiles",
            "TipTrackingSnapshots",
            safe_run_id
        )
        os.makedirs(picture_dir, exist_ok=True)

        filename = f"{safe_barcode}_{timestamp}"
        metadata_path = os.path.join(picture_dir, filename + ".json")

        used_positions = self.GetUsedPositions(barcode)
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        metadata = (
            '{' +
            '"barcode":{},"runId":{},"usedPositions":{},"timestamp":{}'.format(
                self._json_escape(barcode),
                self._json_escape(run_id or ""),
                self._json_escape(used_positions),
                self._json_escape(now_str)
            ) +
            '}'
        )

        with open(metadata_path, 'w', encoding='utf-8') as f:
            f.write(metadata)

        return metadata_path

    # ----------------------------------------------------------------
    #  Helpers
    # ----------------------------------------------------------------

    @staticmethod
    def _parse_positions(csv: str) -> list:
        if not csv or not csv.strip():
            return []
        parts = [s.strip().upper() for s in csv.split(",") if s.strip()]
        # Deduplicate while preserving order
        seen = set()
        result = []
        for p in parts:
            if p not in seen:
                seen.add(p)
                result.append(p)
        return result

    @staticmethod
    def _sort_positions(positions) -> list:
        def sort_key(p):
            if len(p) < 2:
                return (p, 0)
            row = p[0]
            try:
                col = int(p[1:])
            except ValueError:
                col = 0
            return (row, col)
        return sorted(positions, key=sort_key)

    @staticmethod
    def _record_to_json(row) -> str:
        """Convert a DB row (id, barcode, used_positions, tip_type, method_name, method_guid, timestamp) to JSON."""
        return (
            '{' +
            '"id":{},"barcode":{},"positions":{},"tipType":{},"methodName":{},"methodGuid":{},"timestamp":{}'.format(
                row[0],
                BarcodedTipTrackingEngine._json_escape(row[1] or ""),
                BarcodedTipTrackingEngine._json_escape(row[2] or ""),
                BarcodedTipTrackingEngine._json_escape(row[3] or ""),
                BarcodedTipTrackingEngine._json_escape(row[4] or ""),
                BarcodedTipTrackingEngine._json_escape(row[5] or ""),
                BarcodedTipTrackingEngine._json_escape(row[6] or "")
            ) +
            '}'
        )

    @staticmethod
    def _json_escape(value: str) -> str:
        if value is None:
            return "null"
        return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'

    @staticmethod
    def _sanitize_filename(input_str: str) -> str:
        return re.sub(r'[<>:"/\\|?*]', '_', input_str)


# ============================================================================
# Generic fallback COM object (property bag)
# ============================================================================

class GenericComObject:
    """Fallback COM object stub -- stores properties, logs method calls."""
    def __init__(self, prog_id: str = ""):
        self.prog_id = prog_id
        self._properties: dict[str, Any] = {}

    def __getattr__(self, name):
        if name.startswith('_') or name == 'prog_id':
            return super().__getattribute__(name)
        return self._properties.get(name, None)

    def __setattr__(self, name, value):
        if name.startswith('_') or name == 'prog_id':
            super().__setattr__(name, value)
        else:
            self._properties[name] = value
