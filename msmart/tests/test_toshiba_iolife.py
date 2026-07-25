import unittest
from unittest.mock import AsyncMock

from msmart.device import ToshibaIoLifeAirConditioner
from msmart.device.ToshibaIoLife.command import (
    GetPropertiesCommand, GetStateCommand, PropertiesResponse,
    SetStateCommand, StateResponse, ToshibaProperty)


class TestToshibaIoLifeCommands(unittest.TestCase):
    RESPONSE = bytes.fromhex(
        "55aacc33280001ac0000000000000380c0002066b47fff7fff"
        "002b00646efff2000000f0f0000000009f10e3"
    )

    def test_query_frame(self) -> None:
        data = GetStateCommand(message_id=1).tobytes()
        self.assertEqual(data.hex(), (
            "55aacc33240001ac0000000000000300418100ff000000000000"
            "0000000000000000000001abe055"
        ))

    def test_control_frame(self) -> None:
        data = SetStateCommand([(0x01, 1)], message_id=1).tobytes()
        self.assertEqual(data[:18], bytes.fromhex(
            "55aacc33160001ac0000000000000200b001"))
        self.assertEqual(data[18:22], bytes.fromhex("01000101"))

    def test_property_query_frame(self) -> None:
        data = GetPropertiesCommand(
            [ToshibaProperty.POWER, ToshibaProperty.MODE],
            message_id=1,
        ).tobytes()
        self.assertEqual(data.hex(), (
            "55aacc33160001ac0000000000000300b10201000200010c8cb9"
        ))

    def test_property_response(self) -> None:
        data = bytes.fromhex(
            "55aacc33170001ac0000000000000280"
            "b0010800000101009dad7e"
        )
        response = PropertiesResponse(data)
        self.assertEqual(response.properties[ToshibaProperty.SWING_UD], b"\x01")
        self.assertEqual(response.errors, {})

    def test_parse_known_response(self) -> None:
        response = StateResponse(self.RESPONSE)
        self.assertFalse(response.power_on)
        self.assertEqual(response.operational_mode, 2)
        self.assertEqual(response.fan_speed, 102)
        self.assertEqual(response.target_temperature, 26.0)
        self.assertEqual(response.indoor_temperature, 30.2)
        self.assertIsNone(response.outdoor_temperature)
        self.assertFalse(response.self_clean_active)


class TestToshibaIoLifeDevice(unittest.IsolatedAsyncioTestCase):
    def test_confirmed_capabilities(self) -> None:
        device = ToshibaIoLifeAirConditioner(
            ip="127.0.0.1", port=6444, device_id=1)

        self.assertTrue(device.supports_eco)
        self.assertTrue(device.supports_purifier)
        self.assertTrue(device.supports_breezeless)
        self.assertTrue(device.supports_humidity)
        self.assertTrue(device.supports_self_clean)
        self.assertFalse(device.supports_display_control)
        self.assertEqual(
            device.supported_rate_selects,
            [device.RateSelect.OFF, device.RateSelect.GEAR_50],
        )

    async def test_refresh(self) -> None:
        device = ToshibaIoLifeAirConditioner(
            ip="127.0.0.1", port=6444, device_id=1)
        device._lan.send = AsyncMock(return_value=[
            TestToshibaIoLifeCommands.RESPONSE])

        await device.refresh()

        self.assertTrue(device.online)
        self.assertTrue(device.supported)
        self.assertEqual(device.target_temperature, 26.0)
