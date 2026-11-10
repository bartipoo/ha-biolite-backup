"""Decode BioLite's proprietary HomeCharge.device-state binary blob.

The blob is a sequence of TLV records: [tag(1)][field_id(1)][size(2, LE)]
[value(size bytes)]. Two of these records (tag=0x09, field_id=0x0f) hold a
nested sequence of fixed 30-byte "power stage" records instead of a scalar:
[name, null-padded to 16 bytes][idx(1)][a(f32)][b(f32)][c(f32)][flag(1)].

Confirmed empirically by diffing samples against the BioLite app's displayed
values -- there is no public schema for this format. `a` matches the app's
displayed watts closely (within ~1-20%, consistent with sensor/polling-time
noise); `flag` indicates which path is active (e.g. grid passthrough vs
battery-inverter sourced), not simply "on/off"; `field_id=0x09` scalar in
each top-level block matches the app's displayed state-of-charge percentage
(as a 0.0-1.0 fraction) for that block's battery module.
"""
from __future__ import annotations

import base64
import struct
from dataclasses import dataclass


def _f32(data: bytes) -> float:
    return struct.unpack("<f", data)[0]


@dataclass
class PowerStage:
    name: str
    idx: int
    value: float
    limit_b: float
    limit_c: float
    flag: int


@dataclass
class DeviceStateBlock:
    fields: dict[int, float | int]
    stages: dict[str, PowerStage]

    @property
    def soc(self) -> float | None:
        """State of charge as a 0-100 percentage, or None if not present."""
        from .const import FIELD_SOC

        value = self.fields.get(FIELD_SOC)
        return None if value is None else value * 100

    @property
    def temperature(self) -> float | None:
        from .const import FIELD_TEMPERATURE

        return self.fields.get(FIELD_TEMPERATURE)

    @property
    def capacity_wh(self) -> float | None:
        from .const import FIELD_CAPACITY

        return self.fields.get(FIELD_CAPACITY)


def _parse_records(data: bytes, start: int) -> tuple[list[tuple[int, int, int, bytes]], int]:
    """Parse TLV records starting at `start` until one doesn't fit."""
    records = []
    i = start
    n = len(data)
    while i + 4 <= n:
        tag, field_id, size = data[i], data[i + 1], data[i + 2] | (data[i + 3] << 8)
        if tag not in (0x09, 0x0A) or i + 4 + size > n:
            break
        value = data[i + 4 : i + 4 + size]
        records.append((tag, field_id, size, value))
        i += 4 + size
    return records, i


def _decode_stage_blob(blob: bytes) -> dict[str, PowerStage]:
    stages: dict[str, PowerStage] = {}
    for offset in range(0, len(blob) - 29, 30):
        record = blob[offset : offset + 30]
        if len(record) < 30:
            break
        name = record[:16].split(b"\x00")[0].decode("ascii", "replace")
        stages[name] = PowerStage(
            name=name,
            idx=record[16],
            value=_f32(record[17:21]),
            limit_b=_f32(record[21:25]),
            limit_c=_f32(record[25:29]),
            flag=record[29],
        )
    return stages


def parse_device_state(b64_blob: str) -> list[DeviceStateBlock]:
    """Parse the base64 device-state string into its top-level blocks.

    Returns one DeviceStateBlock per TLV run found in the data -- in
    practice this has been the Core unit's block first, then the attached
    Extend battery's block, but that split isn't guaranteed by the format
    itself, just observed. Callers should match blocks by which power
    stages they contain (e.g. "ac_in" present => Core) rather than by
    position, in case BioLite ships a unit without an Extend pack attached.
    """
    data = base64.b64decode(b64_blob)
    blocks: list[DeviceStateBlock] = []
    pos = 0
    n = len(data)
    while pos < n:
        records, end = _parse_records(data, pos)
        if not records:
            pos += 1
            continue
        fields: dict[int, float | int] = {}
        stages: dict[str, PowerStage] = {}
        for tag, field_id, size, value in records:
            if size == 1:
                fields[field_id] = value[0]
            elif size == 4:
                fields[field_id] = _f32(value)
            elif tag == 0x09 and field_id == 0x0F:
                stages = _decode_stage_blob(value)
            # size == 8 all-zero end markers and the leading 15-byte 0x03
            # record are intentionally dropped -- not yet decoded, not
            # needed for sensor values.
        if stages or fields:
            blocks.append(DeviceStateBlock(fields=fields, stages=stages))
        pos = end
    return blocks
