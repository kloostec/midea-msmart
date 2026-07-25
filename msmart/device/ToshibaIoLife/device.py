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

    _EXTENDED_PROPERTIES = (
        ToshibaProperty.WIND_DEFLECTOR,
        ToshibaProperty.DEHUMIDIFY,
        ToshibaProperty.NEW_NO_WIND_SENSE,
        ToshibaProperty.WIND_RADAR,
        ToshibaProperty.AREA,
        ToshibaProperty.WAY_OUT,
        ToshibaProperty.QUICK_MODE,
        ToshibaProperty.AIR_CLEAN_SWITCH,
        ToshibaProperty.TIMER_SELF_CLEAN,
        ToshibaProperty.FAVORITE_MODE,
    )

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
            | AirConditioner.Capability.HUMIDITY
            | AirConditioner.Capability.BREEZELESS
        )
        self._supports_automatic_cleaning = True
        self._automatic_cleaning_enabled: bool | None = None
        self._supported_toshiba_properties: set[ToshibaProperty] = set()
        self._has_extended_state = False
        self._wind_deflector: bytes | None = None
        self._dehumidification_mode: int | None = None
        self._advanced_no_wind_mode: int | None = None
        self._wind_radar_mode: int | None = None
        self._area_mode: int | None = None
        self._way_out_enabled: bool | None = None
        self._quick_mode: bool | None = None
        self._air_clean_active: bool | None = None
        self._air_clean_enabled: bool | None = None
        self._timer_self_clean_enabled: bool | None = None
        self._favorite_mode: bytes | None = None
        self._air_monitor_status: int | None = None
        self._air_monitor_enabled: bool | None = None
        self._radar_active: bool | None = None
        self._uvc_enabled: bool | None = None
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
        self._has_extended_state = response.has_extended_state
        if response.has_extended_state:
            self._quick_mode = response.quick_mode
            self._air_monitor_status = response.air_monitor_status
            self._air_monitor_enabled = response.air_monitor_enabled
            self._advanced_no_wind_mode = response.advanced_no_wind_mode
            self._area_mode = response.area_mode
            self._radar_active = response.radar_active
            self._wind_radar_mode = response.wind_radar_mode
            self._way_out_enabled = response.way_out
            self._air_clean_active = response.air_clean_active
            self._air_clean_enabled = response.air_clean_enabled
            self._uvc_enabled = response.uvc_enabled
        else:
            self._quick_mode = None
            self._air_monitor_status = None
            self._air_monitor_enabled = None
            self._advanced_no_wind_mode = None
            self._area_mode = None
            self._radar_active = None
            self._wind_radar_mode = None
            self._way_out_enabled = None
            self._air_clean_active = None
            self._air_clean_enabled = None
            self._uvc_enabled = None

    def _update_toshiba_properties(self, response: PropertiesResponse) -> None:
        for property_id, value in response.properties.items():
            try:
                prop = ToshibaProperty(property_id)
            except ValueError:
                continue
            self._toshiba_properties[prop] = value
            if value and property_id not in response.errors:
                self._supported_toshiba_properties.add(prop)

        display = response.properties.get(ToshibaProperty.DISPLAY)
        if display:
            self._display_on = display[0] > 0

        automatic_cleaning = response.properties.get(ToshibaProperty.CLEAN)
        if automatic_cleaning:
            self._automatic_cleaning_enabled = automatic_cleaning[0] > 0

        property_targets = (
            (ToshibaProperty.WIND_DEFLECTOR, "_wind_deflector", bytes),
            (ToshibaProperty.DEHUMIDIFY, "_dehumidification_mode", int),
            (ToshibaProperty.NEW_NO_WIND_SENSE,
             "_advanced_no_wind_mode", int),
            (ToshibaProperty.WIND_RADAR, "_wind_radar_mode", int),
            (ToshibaProperty.AREA, "_area_mode", int),
            (ToshibaProperty.WAY_OUT, "_way_out_enabled", bool),
            (ToshibaProperty.QUICK_MODE, "_quick_mode", bool),
            (ToshibaProperty.TIMER_SELF_CLEAN,
             "_timer_self_clean_enabled", bool),
            (ToshibaProperty.FAVORITE_MODE, "_favorite_mode", bytes),
        )
        for property_id, attribute, value_type in property_targets:
            value = response.properties.get(property_id)
            if not value:
                continue
            parsed = (
                value
                if value_type is bytes
                else value[0] > 0
                if value_type is bool
                else value[0]
            )
            setattr(self, attribute, parsed)

    async def refresh(self) -> None:
        responses = await self._send_command(GetStateCommand())
        responses.extend(await self._send_command(
            GetPropertiesCommand([
                ToshibaProperty.DISPLAY,
                ToshibaProperty.CLEAN,
                *self._EXTENDED_PROPERTIES,
            ])))
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
            *self._EXTENDED_PROPERTIES,
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
        self._supports_automatic_cleaning = (
            ToshibaProperty.CLEAN in properties
            and bool(properties[ToshibaProperty.CLEAN])
        )
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

    @property
    def supports_automatic_cleaning(self) -> bool:
        """Return whether automatic cleaning after shutdown is supported."""
        return self._supports_automatic_cleaning

    @property
    def automatic_cleaning_enabled(self) -> bool | None:
        """Return the persistent automatic-cleaning preference."""
        return self._automatic_cleaning_enabled

    async def set_automatic_cleaning(self, enabled: bool) -> None:
        """Enable or disable automatic cleaning after shutdown."""
        await self.set_toshiba_properties({
            # IoLIFE writes a two-byte cleanAutoValue. The second byte is
            # reserved and reported as FF by the appliance.
            ToshibaProperty.CLEAN: bytes((int(enabled), 0xFF)),
        })

    async def enable_automatic_cleaning(self) -> None:
        """Enable automatic cleaning after shutdown."""
        await self.set_automatic_cleaning(True)

    async def disable_automatic_cleaning(self) -> None:
        """Disable automatic cleaning after shutdown."""
        await self.set_automatic_cleaning(False)

    @property
    def supported_toshiba_properties(self) -> tuple[ToshibaProperty, ...]:
        """Return Toshiba-specific properties confirmed by the appliance."""
        return tuple(sorted(
            self._supported_toshiba_properties,
            key=int,
        ))

    def supports_toshiba_property(
        self,
        property_id: ToshibaProperty | int,
    ) -> bool:
        """Return whether a Toshiba-specific property returned a value."""
        return ToshibaProperty(property_id) in self._supported_toshiba_properties

    @property
    def wind_deflector(self) -> bytes | None:
        return (
            self._wind_deflector
            if self.supports_toshiba_property(ToshibaProperty.WIND_DEFLECTOR)
            else None
        )

    @property
    def dehumidification_mode(self) -> int | None:
        return (
            self._dehumidification_mode
            if self.supports_toshiba_property(ToshibaProperty.DEHUMIDIFY)
            else None
        )

    @property
    def advanced_no_wind_mode(self) -> int | None:
        return (
            self._advanced_no_wind_mode
            if self.supports_toshiba_property(
                ToshibaProperty.NEW_NO_WIND_SENSE
            )
            else None
        )

    @property
    def wind_radar_mode(self) -> int | None:
        return (
            self._wind_radar_mode
            if self.supports_toshiba_property(ToshibaProperty.WIND_RADAR)
            else None
        )

    @property
    def radar_active(self) -> bool | None:
        return (
            self._radar_active
            if self.supports_toshiba_property(ToshibaProperty.WIND_RADAR)
            else None
        )

    @property
    def area_mode(self) -> int | None:
        return (
            self._area_mode
            if self.supports_toshiba_property(ToshibaProperty.AREA)
            else None
        )

    @property
    def way_out_enabled(self) -> bool | None:
        return (
            self._way_out_enabled
            if self.supports_toshiba_property(ToshibaProperty.WAY_OUT)
            else None
        )

    @property
    def quick_mode(self) -> bool | None:
        return (
            self._quick_mode
            if self.supports_toshiba_property(ToshibaProperty.QUICK_MODE)
            else None
        )

    @property
    def air_monitor_status(self) -> int | None:
        return self._air_monitor_status if self._has_extended_state else None

    @property
    def air_monitor_enabled(self) -> bool | None:
        return self._air_monitor_enabled if self._has_extended_state else None

    @property
    def air_clean_active(self) -> bool | None:
        return (
            self._air_clean_active
            if self.supports_toshiba_property(ToshibaProperty.AIR_CLEAN_SWITCH)
            else None
        )

    @property
    def air_clean_enabled(self) -> bool | None:
        return (
            self._air_clean_enabled
            if self.supports_toshiba_property(ToshibaProperty.AIR_CLEAN_SWITCH)
            else None
        )

    @property
    def uvc_enabled(self) -> bool | None:
        return self._uvc_enabled if self._has_extended_state else None

    @property
    def timer_self_clean_enabled(self) -> bool | None:
        return (
            self._timer_self_clean_enabled
            if self.supports_toshiba_property(ToshibaProperty.TIMER_SELF_CLEAN)
            else None
        )

    @property
    def favorite_mode(self) -> bytes | None:
        return (
            self._favorite_mode
            if self.supports_toshiba_property(ToshibaProperty.FAVORITE_MODE)
            else None
        )

    def to_dict(self) -> dict:
        """Return standard AC state plus Toshiba IoLIFE extensions."""
        return {
            **super().to_dict(),
            "automatic_cleaning_enabled": self.automatic_cleaning_enabled,
            "supported_toshiba_properties": [
                prop.name.lower()
                for prop in self.supported_toshiba_properties
            ],
            "wind_deflector": (
                self.wind_deflector.hex()
                if self.wind_deflector is not None
                else None
            ),
            "dehumidification_mode": self.dehumidification_mode,
            "advanced_no_wind_mode": self.advanced_no_wind_mode,
            "wind_radar_mode": self.wind_radar_mode,
            "radar_active": self.radar_active,
            "area_mode": self.area_mode,
            "way_out_enabled": self.way_out_enabled,
            "quick_mode": self.quick_mode,
            "air_monitor_status": self.air_monitor_status,
            "air_monitor_enabled": self.air_monitor_enabled,
            "air_clean_active": self.air_clean_active,
            "air_clean_enabled": self.air_clean_enabled,
            "uvc_enabled": self.uvc_enabled,
            "timer_self_clean_enabled": self.timer_self_clean_enabled,
            "favorite_mode": (
                self.favorite_mode.hex()
                if self.favorite_mode is not None
                else None
            ),
        }

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
