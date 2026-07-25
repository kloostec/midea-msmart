"""Local support for Japanese Toshiba IoLIFE air conditioners."""

from __future__ import annotations

import logging

from msmart.device.AC.device import AirConditioner
from msmart.utils import CapabilityManager

from .command import (
    GetPropertiesCommand,
    GetStateCommand,
    PropertiesResponse,
    SetStateCommand,
    StateResponse,
    ToshibaProperty,
)

_LOGGER = logging.getLogger(__name__)


class ToshibaIoLifeAirConditioner(AirConditioner):
    """Toshiba AC using 55AACC33 appliance frames over Midea V3 transport."""

    is_toshiba_iolife = True

    _FAN_SPEED_VALUES = {
        AirConditioner.FanSpeed.AUTO: 0x66,
        AirConditioner.FanSpeed.MAX: 0x50,
        AirConditioner.FanSpeed.HIGH: 0x50,
        AirConditioner.FanSpeed.MEDIUM: 0x3C,
        AirConditioner.FanSpeed.LOW: 0x14,
        AirConditioner.FanSpeed.SILENT: 0x01,
    }

    def __init__(self, ip: str, device_id: int, port: int, **kwargs) -> None:
        kwargs.pop("device_type", None)
        super().__init__(ip=ip, device_id=device_id, port=port, **kwargs)
        self._capabilities = CapabilityManager(
            AirConditioner.Capability.ECO
            | AirConditioner.Capability.PURIFIER
            | AirConditioner.Capability.FILTER_REMINDER
            | AirConditioner.Capability.SELF_CLEAN
            | AirConditioner.Capability.HUMIDITY
            | AirConditioner.Capability.BREEZELESS
        )
        self._supported_op_modes = [
            AirConditioner.OperationalMode.AUTO,
            AirConditioner.OperationalMode.COOL,
            AirConditioner.OperationalMode.DRY,
            AirConditioner.OperationalMode.HEAT,
            AirConditioner.OperationalMode.FAN_ONLY,
        ]
        self._supported_swing_modes = [
            AirConditioner.SwingMode.OFF,
            AirConditioner.SwingMode.VERTICAL,
            AirConditioner.SwingMode.HORIZONTAL,
            AirConditioner.SwingMode.BOTH,
        ]
        self._supported_fan_speeds = [
            AirConditioner.FanSpeed.AUTO,
            AirConditioner.FanSpeed.HIGH,
            AirConditioner.FanSpeed.MEDIUM,
            AirConditioner.FanSpeed.LOW,
            AirConditioner.FanSpeed.SILENT,
        ]
        self._supported_rate_selects = [
            AirConditioner.RateSelect.OFF,
            AirConditioner.RateSelect.GEAR_50,
        ]
        self._toshiba_properties: dict[ToshibaProperty, bytes] = {}

    def _update_toshiba_state(self, response: StateResponse) -> None:
        self._power_state = response.power_on
        self._target_temperature = response.target_temperature
        self._operational_mode = AirConditioner.OperationalMode.get_from_value(
            response.operational_mode)
        self._fan_speed = AirConditioner.FanSpeed.get_from_value(
            response.fan_speed)
        self._swing_mode = AirConditioner.SwingMode.get_from_value(
            response.swing_mode)
        self._indoor_temperature = response.indoor_temperature
        self._outdoor_temperature = response.outdoor_temperature
        self._indoor_humidity = response.indoor_humidity
        self._eco = response.eco
        self._purifier = response.purifier
        self._self_clean_active = response.self_clean_active
        self._filter_alert = response.filter_alert
        self._error_code = response.error_code
        self._rate_select = AirConditioner.RateSelect.get_from_value(
            response.rate_select)
        self._breeze_mode = (
            AirConditioner.BreezeMode.BREEZELESS
            if response.no_wind_sense
            else AirConditioner.BreezeMode.OFF
        )

    def _update_toshiba_properties(self, response: PropertiesResponse) -> None:
        for property_id, value in response.properties.items():
            try:
                prop = ToshibaProperty(property_id)
            except ValueError:
                continue
            self._toshiba_properties[prop] = value

        display = response.properties.get(ToshibaProperty.DISPLAY)
        if display:
            self._display_on = display[0] > 0

    async def refresh(self) -> None:
        responses = await self._send_command(GetStateCommand())
        responses.extend(await self._send_command(
            GetPropertiesCommand([ToshibaProperty.DISPLAY])))
        valid = 0
        for data in responses:
            try:
                response = StateResponse(data)
            except ValueError:
                try:
                    properties = PropertiesResponse(data)
                except ValueError as error:
                    _LOGGER.debug(
                        "Ignored Toshiba response from device %s: %s",
                        self.id, error)
                else:
                    self._update_toshiba_properties(properties)
            else:
                self._update_toshiba_state(response)
                valid += 1

        self._online = valid > 0
        self._supported |= self._online

    async def get_capabilities(self) -> None:
        """IoLIFE does not expose the standard Midea capability request."""
        properties = await self.get_toshiba_properties([
            ToshibaProperty.ECO,
            ToshibaProperty.PURIFIER,
            ToshibaProperty.INDOOR_HUMIDITY,
            ToshibaProperty.DISPLAY,
            ToshibaProperty.NO_WIND_SENSE,
            ToshibaProperty.FILTER,
            ToshibaProperty.CLEAN,
            ToshibaProperty.RATE_SELECT,
        ])
        self._capabilities.set(
            AirConditioner.Capability.ECO,
            bool(properties.get(ToshibaProperty.ECO)))
        self._capabilities.set(
            AirConditioner.Capability.PURIFIER,
            bool(properties.get(ToshibaProperty.PURIFIER)))
        self._capabilities.set(
            AirConditioner.Capability.HUMIDITY,
            bool(properties.get(ToshibaProperty.INDOOR_HUMIDITY)))
        # DISPLAY returns a value, but control writes are ignored by these
        # IoLIFE adapters. Keep it available through the raw property API
        # without advertising standard Midea display control.
        self._capabilities.set(
            AirConditioner.Capability.DISPLAY_CONTROL, False)
        self._capabilities.set(
            AirConditioner.Capability.BREEZELESS,
            bool(properties.get(ToshibaProperty.NO_WIND_SENSE)))
        self._capabilities.set(
            AirConditioner.Capability.FILTER_REMINDER,
            bool(properties.get(ToshibaProperty.FILTER)))
        self._capabilities.set(
            AirConditioner.Capability.SELF_CLEAN,
            bool(properties.get(ToshibaProperty.CLEAN)))
        if properties.get(ToshibaProperty.RATE_SELECT):
            self._supported_rate_selects = [
                AirConditioner.RateSelect.OFF,
                AirConditioner.RateSelect.GEAR_50,
            ]
        else:
            self._supported_rate_selects = [AirConditioner.RateSelect.OFF]

        await self.refresh()

    async def get_toshiba_properties(
        self,
        properties: list[ToshibaProperty | int] | None = None,
    ) -> dict[ToshibaProperty, bytes]:
        """Query raw IoLIFE properties, including Toshiba-specific features."""
        requested = properties or list(ToshibaProperty)
        result: dict[ToshibaProperty, bytes] = {}
        for offset in range(0, len(requested), 16):
            responses = await self._send_command(
                GetPropertiesCommand(requested[offset:offset + 16]))
            for data in responses:
                try:
                    response = PropertiesResponse(data)
                except ValueError:
                    continue
                self._update_toshiba_properties(response)
                for property_id, value in response.properties.items():
                    try:
                        result[ToshibaProperty(property_id)] = value
                    except ValueError:
                        continue
        return result

    async def set_toshiba_properties(
        self,
        properties: dict[ToshibaProperty | int, int | bytes],
        *,
        refresh: bool = True,
    ) -> None:
        """Set raw IoLIFE properties for model-specific features."""
        await self._send_command(SetStateCommand(list(properties.items())))
        if refresh:
            await self.refresh()

    @property
    def toshiba_properties(self) -> dict[ToshibaProperty, bytes]:
        """Return the most recently queried raw IoLIFE properties."""
        return dict(self._toshiba_properties)

    async def toggle_display(self) -> None:
        _LOGGER.warning(
            "Device %s reports display state but ignores display control.",
            self.id)

    async def set_self_clean(self, enabled: bool) -> None:
        """Enable or disable the Toshiba cleaning function."""
        await self.set_toshiba_properties({
            ToshibaProperty.CLEAN: int(enabled),
        })

    async def start_self_clean(self) -> None:
        """Enable the Toshiba cleaning function."""
        await self.set_self_clean(True)

    async def stop_self_clean(self) -> None:
        """Disable the Toshiba cleaning function."""
        await self.set_self_clean(False)

    async def apply(self) -> None:
        if self._operational_mode not in self._supported_op_modes:
            raise ValueError(
                f"Unsupported Toshiba operation mode: {self._operational_mode}")
        if self._fan_speed not in self._supported_fan_speeds:
            raise ValueError(
                f"Unsupported Toshiba fan speed: {self._fan_speed}")
        if self._swing_mode not in self._supported_swing_modes:
            raise ValueError(
                f"Unsupported Toshiba swing mode: {self._swing_mode}")
        if self._rate_select not in self._supported_rate_selects:
            raise ValueError(
                f"Unsupported Toshiba rate selection: {self._rate_select}")
        if self._breeze_mode not in (
            AirConditioner.BreezeMode.OFF,
            AirConditioner.BreezeMode.BREEZELESS,
        ):
            raise ValueError(
                f"Unsupported Toshiba breeze mode: {self._breeze_mode}")

        unsupported_enabled = {
            "beep": self._beep_on,
            "fahrenheit": self._fahrenheit_unit,
            "turbo": self._turbo,
            "freeze protection": self._freeze_protection,
            "sleep": self._sleep,
            "follow me": self._follow_me,
            "iECO": self._ieco,
            "flash": self._flash,
            "outdoor silent": self._out_silent,
            "auxiliary heat": self._aux_mode != AirConditioner.AuxHeatMode.OFF,
        }
        for feature, enabled in unsupported_enabled.items():
            if enabled:
                _LOGGER.warning(
                    "Toshiba IoLIFE device %s does not expose %s control.",
                    self.id, feature)

        fan_speed = self._FAN_SPEED_VALUES.get(self._fan_speed)
        if fan_speed is None:
            raise ValueError(f"Unsupported Toshiba fan speed: {self._fan_speed}")

        swing_ud = 1 if self._swing_mode in (
            AirConditioner.SwingMode.VERTICAL, AirConditioner.SwingMode.BOTH) else 0
        swing_lr = 1 if self._swing_mode in (
            AirConditioner.SwingMode.HORIZONTAL, AirConditioner.SwingMode.BOTH) else 0

        properties = [
            (ToshibaProperty.POWER, int(bool(self._power_state))),
            (ToshibaProperty.MODE, int(self._operational_mode)),
            (ToshibaProperty.TEMPERATURE,
             round(float(self._target_temperature) * 2)),
            (ToshibaProperty.FAN_SPEED, fan_speed),
            (ToshibaProperty.SWING_UD, swing_ud),
            (ToshibaProperty.SWING_LR, swing_lr),
            (ToshibaProperty.ECO, int(bool(self._eco))),
            (ToshibaProperty.PURIFIER, int(bool(self._purifier))),
        ]
        if self.supports_breezeless:
            properties.append((
                ToshibaProperty.NO_WIND_SENSE,
                int(self._breeze_mode == AirConditioner.BreezeMode.BREEZELESS),
            ))
        if self._supported_rate_selects != [AirConditioner.RateSelect.OFF]:
            properties.append((
                ToshibaProperty.RATE_SELECT,
                int(self._rate_select),
            ))
        await self._send_command(SetStateCommand(properties))
        self._updated_properties.clear()
        await self.refresh()
