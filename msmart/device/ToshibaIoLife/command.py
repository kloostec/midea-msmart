"""Toshiba IoLIFE AC commands carried by a Midea V3 LAN connection."""

from __future__ import annotations

import itertools
from enum import IntEnum

_CRC8_854_TABLE = (
    0, 94, 188, 226, 97, 63, 221, 131, 194, 156, 126, 32, 163, 253, 31, 65,
    157, 195, 33, 127, 252, 162, 64, 30, 95, 1, 227, 189, 62, 96, 130, 220,
    35, 125, 159, 193, 66, 28, 254, 160, 225, 191, 93, 3, 128, 222, 60, 98,
    190, 224, 2, 92, 223, 129, 99, 61, 124, 34, 192, 158, 29, 67, 161, 255,
    70, 24, 250, 164, 39, 121, 155, 197, 132, 218, 56, 102, 229, 187, 89, 7,
    219, 133, 103, 57, 186, 228, 6, 88, 25, 71, 165, 251, 120, 38, 196, 154,
    101, 59, 217, 135, 4, 90, 184, 230, 167, 249, 27, 69, 198, 152, 122, 36,
    248, 166, 68, 26, 153, 199, 37, 123, 58, 100, 134, 216, 91, 5, 231, 185,
    140, 210, 48, 110, 237, 179, 81, 15, 78, 16, 242, 172, 47, 113, 147, 205,
    17, 79, 173, 243, 112, 46, 204, 146, 211, 141, 111, 49, 178, 236, 14, 80,
    175, 241, 19, 77, 206, 144, 114, 44, 109, 51, 209, 143, 12, 82, 176, 238,
    50, 108, 142, 208, 83, 13, 239, 177, 240, 174, 76, 18, 145, 207, 45, 115,
    202, 148, 118, 40, 171, 245, 23, 73, 8, 86, 180, 234, 105, 55, 213, 139,
    87, 9, 235, 181, 54, 104, 138, 212, 149, 203, 41, 119, 244, 170, 72, 22,
    233, 183, 85, 11, 136, 214, 52, 106, 43, 117, 151, 201, 74, 20, 246, 168,
    116, 42, 200, 150, 21, 75, 169, 247, 182, 232, 10, 84, 215, 137, 107, 53,
)

_MESSAGE_IDS = itertools.cycle(range(1, 255))


class ToshibaProperty(IntEnum):
    """Known Toshiba IoLIFE AC property identifiers."""

    POWER = 0x01
    MODE = 0x02
    TEMPERATURE = 0x03
    INDOOR_TEMPERATURE = 0x04
    OUTDOOR_TEMPERATURE = 0x05
    FAN_SPEED = 0x06
    FAN_SPEED_REAL = 0x07
    SWING_UD = 0x08
    SWING_LR = 0x09
    WIND_DEFLECTOR = 0x0A
    POWER_ON_TIMER = 0x0B
    POWER_OFF_TIMER = 0x0C
    ECO = 0x0D
    PURIFIER = 0x0E
    DRY = 0x10
    HUMIDITY = 0x14
    INDOOR_HUMIDITY = 0x15
    DISPLAY = 0x17
    NO_WIND_SENSE = 0x18
    BUZZER = 0x1A
    COOL_HEAT_SENSE = 0x21
    AI_STUDY_CONTROL = 0x22
    AI_STUDY_TEMPERATURE = 0x23
    NOBODY_ENERGY_SAVE = 0x30
    WIND_STRAIGHT = 0x32
    WIND_AVOID = 0x33
    FILTER = 0x3D
    ERROR_CODE = 0x3F
    MODE_QUERY = 0x41
    CLEAN = 0x46
    HIGH_TEMPERATURE_MONITOR = 0x47
    RATE_SELECT = 0x48
    ENERGY_SAVE = 0x50
    DEHUMIDIFY = 0x51
    TIMER_DAILY = 0x52
    POWER_ON_TIMER_SPECIFIC = 0x53
    POWER_OFF_TIMER_SPECIFIC = 0x54
    COMFORT_AIRFLOW = 0x55
    TIMER_EXPIRED = 0x60
    TIMER_SETTING = 0x61
    NEW_NO_WIND_SENSE = 0x70
    WIND_RADAR = 0x71
    AREA = 0x72
    WAY_OUT = 0x73
    QUICK_MODE = 0x74
    CHANGE_AIR = 0x75
    AIR_CLEAN_SWITCH = 0x76
    TIMER_SELF_CLEAN = 0x77
    FAVORITE_MODE = 0x78
    CIRCLE_FAN = 0x79
    ECO_POWER_SAVING = 0x7A
    WEAK_COOL = 0x7B
    HIGH_TEMPERATURE_WIND = 0x7C
    MANUAL_DEFROST = 0x7D


def _crc8(data: bytes) -> int:
    crc = 0
    for value in data:
        crc = _CRC8_854_TABLE[(crc ^ value) & 0xFF]
    return crc


def _crc16(data: bytes) -> int:
    crc = 0
    for value in data:
        crc ^= value << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _frame(body: bytes, request_type: int) -> bytes:
    message = bytearray(16 + len(body) + 2)
    message[:4] = b"\x55\xAA\xCC\x33"
    message[4:6] = (len(message) - 4).to_bytes(2, "little")
    message[6:8] = b"\x01\xAC"
    message[14:16] = request_type.to_bytes(2, "little")
    message[16:-2] = body
    message[-2:] = _crc16(message[:-2]).to_bytes(2, "little")
    return bytes(message)


class GetStateCommand:
    """Request the complete Toshiba AC state."""

    def __init__(self, message_id: int | None = None) -> None:
        body = bytearray(22)
        body[0:2] = b"\x41\x81"
        body[3] = 0xFF
        body[20] = next(_MESSAGE_IDS) if message_id is None else message_id
        body[21] = _crc8(body[:-1])
        self._data = _frame(body, 0x0003)

    def tobytes(self) -> bytes:
        return self._data


class GetPropertiesCommand:
    """Query one or more Toshiba properties."""

    def __init__(
        self,
        properties: list[ToshibaProperty | int],
        message_id: int | None = None,
    ) -> None:
        if not properties or len(properties) > 255:
            raise ValueError("One to 255 Toshiba properties are required")
        body = bytearray((0xB1, len(properties)))
        for property_id in properties:
            body.extend((int(property_id), 0))
        body.append(next(_MESSAGE_IDS) if message_id is None else message_id)
        body.append(_crc8(body))
        self._data = _frame(body, 0x0003)

    def tobytes(self) -> bytes:
        return self._data


class SetStateCommand:
    """Set one or more Toshiba property/value pairs."""

    def __init__(
        self,
        properties: list[tuple[ToshibaProperty | int, int | bytes]],
        message_id: int | None = None,
    ) -> None:
        body = bytearray((0xB0, len(properties)))
        for property_id, value in properties:
            value_bytes = (
                bytes((value & 0xFF,)) if isinstance(value, int) else bytes(value)
            )
            if len(value_bytes) > 255:
                raise ValueError("Toshiba property values cannot exceed 255 bytes")
            body.extend((int(property_id), 0, len(value_bytes)))
            body.extend(value_bytes)
        body.append(next(_MESSAGE_IDS) if message_id is None else message_id)
        body.append(_crc8(body))
        self._data = _frame(body, 0x0002)

    def tobytes(self) -> bytes:
        return self._data


class PropertiesResponse:
    """Parsed B0/B1 Toshiba property response."""

    def __init__(self, data: bytes) -> None:
        if len(data) < 24 or data[:4] != b"\x55\xAA\xCC\x33":
            raise ValueError("Not a Toshiba IoLIFE property response")
        if int.from_bytes(data[4:6], "little") != len(data) - 4:
            raise ValueError("Invalid Toshiba IoLIFE response length")
        if _crc16(data[:-2]) != int.from_bytes(data[-2:], "little"):
            raise ValueError("Invalid Toshiba IoLIFE response checksum")
        if data[16] not in (0xB0, 0xB1):
            raise ValueError("Unsupported Toshiba IoLIFE property response")

        count = data[17]
        position = 18
        properties: dict[int, bytes] = {}
        errors: dict[int, int] = {}
        for _ in range(count):
            if position + 4 > len(data) - 4:
                raise ValueError("Truncated Toshiba IoLIFE property response")
            property_id = data[position]
            status = int.from_bytes(data[position + 1:position + 3], "little")
            value_length = data[position + 3]
            position += 4
            if position + value_length > len(data) - 2:
                raise ValueError("Truncated Toshiba IoLIFE property value")
            value = bytes(data[position:position + value_length])
            position += value_length
            properties[property_id] = value
            if status:
                errors[property_id] = status

        self.properties = properties
        self.errors = errors


class StateResponse:
    """Parsed Toshiba C0/D0 state response."""

    _FAN_SPEEDS = {
        0x00: 102,
        0x66: 102,
        0x50: 80,
        0x3C: 60,
        0x14: 40,
        0x01: 20,
    }

    def __init__(self, data: bytes) -> None:
        if len(data) < 39 or data[:4] != b"\x55\xAA\xCC\x33":
            raise ValueError("Not a Toshiba IoLIFE response")
        if int.from_bytes(data[4:6], "little") != len(data) - 4:
            raise ValueError("Invalid Toshiba IoLIFE response length")
        if _crc16(data[:-2]) != int.from_bytes(data[-2:], "little"):
            raise ValueError("Invalid Toshiba IoLIFE response checksum")
        if data[14] not in (0x02, 0x03, 0x05) or data[16] not in (0xC0, 0xD0):
            raise ValueError("Unsupported Toshiba IoLIFE response")

        body = data[16:]
        self.power_on = bool(body[1] & 1)
        self.operational_mode = (body[2] >> 4) & 0x0F
        self.fan_speed = self._FAN_SPEEDS.get(body[3] & 0x7F, 102)
        self.target_temperature = (body[4] & 0x7F) / 2

        swing_lr = body[11] & 0x0F
        swing_ud = (body[11] >> 4) & 0x0F
        self.swing_mode = (0x03 if swing_lr else 0) | (0x0C if swing_ud else 0)
        self.indoor_humidity = None if body[10] == 0xFF else body[10]
        self.rate_select = body[12]
        self.no_wind_sense = body[18] & 0x0F

        decimal = body[15]
        self.indoor_temperature = (
            None if body[13] == 0xFF
            else (body[13] - 50) / 2 + 0.1 * (decimal & 0x0F)
        )
        self.outdoor_temperature = (
            None if body[14] == 0xFF
            else (body[14] - 50) / 2 + 0.1 * ((decimal >> 4) & 0x0F)
        )
        self.eco = bool(body[16] & 0x01)
        self.purifier = bool(body[16] & 0x02)
        # Toshiba reports active manual/automatic cleaning cycles in
        # adjacent bits. The persistent automatic-cleaning preference is
        # queried separately through ToshibaProperty.CLEAN.
        self.self_clean_active = bool(body[16] & 0x30)
        self.filter_alert = bool(body[17] & 0x20)
        self.error_code = body[23] if len(body) > 25 else None
