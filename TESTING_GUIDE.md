# Testing Guide

Це керівництво демонструє, як тестувати різні компоненти інтеграції.

## Тестування Domain Layer (без Home Assistant)

Domain layer повністю незалежний від HA і може тестуватися як звичайний Python код.

### Приклад: Тестування Mode Selection Policy

```python
"""test_mode_selection.py"""
import pytest
from datetime import datetime, timedelta

from custom_components.smart_climate_controller.domain.value_objects import (
    HVACMode,
    Temperature,
    SensorSnapshot,
    DeviceState,
    DeviceCapabilities,
    ControlContext,
    TemperatureRate,
)
from custom_components.smart_climate_controller.domain.policies.mode_selection import (
    OutdoorAwareModeSelectionPolicy,
)


@pytest.fixture
def policy():
    return OutdoorAwareModeSelectionPolicy()


@pytest.fixture
def base_context():
    """Create basic control context for tests."""
    capabilities = DeviceCapabilities(
        can_heat=True,
        can_cool=True,
        can_auto=True,
        can_dry=False,
        can_fan_only=False,
        min_setpoint=Temperature(16.0),
        max_setpoint=Temperature(30.0),
        supported_modes=frozenset([HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]),
    )

    device_state = DeviceState(
        hvac_mode=HVACMode.COOL,
        current_setpoint=Temperature(21.0),
        is_available=True,
    )

    sensor_snapshot = SensorSnapshot(
        room_temperature=Temperature(21.0),
        outdoor_temperature=Temperature(15.0),
        timestamp=datetime.now(),
        temperature_rate=TemperatureRate(0.0),
    )

    return ControlContext(
        sensor_snapshot=sensor_snapshot,
        device_state=device_state,
        device_capabilities=capabilities,
        target_temperature=Temperature(21.0),
        min_room_temp=Temperature(16.0),
        max_room_temp=Temperature(30.0),
        deadband=0.5,
        base_offset=2.0,
        dynamic_rate_factor=10.0,
        max_dynamic_offset=5.0,
        outdoor_heat_threshold=12.0,
        outdoor_cool_threshold=18.0,
        mode_switch_hysteresis=1.0,
        min_mode_switch_interval=1800,
        min_command_interval=30,
        last_mode_change=None,
        last_command_sent=None,
        controller_enabled=True,
        now=datetime.now(),
    )


def test_mode_preserved_in_deadband(policy, base_context):
    """Test that current mode is preserved when in deadband."""
    # Room at target, outdoor neutral
    mode, reason = policy.select_mode(
        current_mode=HVACMode.COOL,
        room_temp=Temperature(21.0),
        target_temp=Temperature(21.0),
        outdoor_temp=Temperature(15.0),
        context=base_context,
    )

    assert mode == HVACMode.COOL
    assert "preserving" in reason.lower()


def test_cooling_when_outdoor_warm(policy, base_context):
    """Test cooling selected when outdoor warm and room needs cooling."""
    mode, reason = policy.select_mode(
        current_mode=HVACMode.OFF,
        room_temp=Temperature(24.0),  # Too warm
        target_temp=Temperature(21.0),
        outdoor_temp=Temperature(25.0),  # Warm outside
        context=base_context,
    )

    assert mode == HVACMode.COOL
    assert "cooling needed" in reason.lower()


def test_heating_when_outdoor_cold(policy, base_context):
    """Test heating selected when outdoor cold and room needs heating."""
    mode, reason = policy.select_mode(
        current_mode=HVACMode.OFF,
        room_temp=Temperature(18.0),  # Too cold
        target_temp=Temperature(21.0),
        outdoor_temp=Temperature(5.0),  # Cold outside
        context=base_context,
    )

    assert mode == HVACMode.HEAT
    assert "heating needed" in reason.lower()


def test_mode_switch_locked(policy, base_context):
    """Test that mode cannot switch too soon."""
    # Set last mode change to 10 minutes ago (min interval is 30 minutes)
    context = base_context
    now = datetime.now()
    context = context.__class__(
        **{**context.__dict__,
           'last_mode_change': now - timedelta(minutes=10),
           'now': now}
    )

    mode, reason = policy.select_mode(
        current_mode=HVACMode.HEAT,
        room_temp=Temperature(24.0),  # Would normally switch to cool
        target_temp=Temperature(21.0),
        outdoor_temp=Temperature(25.0),
        context=context,
    )

    # Should keep current mode due to lock
    assert mode == HVACMode.HEAT
    assert "locked" in reason.lower()


def test_hysteresis_prevents_oscillation(policy, base_context):
    """Test that hysteresis prevents mode oscillation in neutral zone."""
    # Currently cooling, outdoor in neutral zone
    mode, reason = policy.select_mode(
        current_mode=HVACMode.COOL,
        room_temp=Temperature(21.3),  # Slightly warm but in deadband
        target_temp=Temperature(21.0),
        outdoor_temp=Temperature(15.0),  # Between heat and cool thresholds
        context=base_context,
    )

    # Should preserve cooling mode
    assert mode == HVACMode.COOL
```

### Приклад: Тестування Setpoint Calculation

```python
"""test_setpoint_adjustment.py"""
import pytest
from custom_components.smart_climate_controller.domain.value_objects import (
    HVACMode,
    Temperature,
)
from custom_components.smart_climate_controller.domain.policies.setpoint_adjustment import (
    DynamicSetpointAdjustmentPolicy,
)


@pytest.fixture
def policy():
    return DynamicSetpointAdjustmentPolicy()


def test_cooling_setpoint_with_large_error(policy, base_context):
    """Test that large temperature error increases cooling setpoint offset."""
    setpoint, reason = policy.calculate_setpoint(
        mode=HVACMode.COOL,
        room_temp=Temperature(26.0),  # 5°C above target
        target_temp=Temperature(21.0),
        temp_rate=None,
        context=base_context,
    )

    # Setpoint should be significantly below target for aggressive cooling
    assert setpoint.value < 21.0
    assert setpoint.value < 19.0  # With large error, offset should be substantial


def test_heating_setpoint_with_rising_temp(policy, base_context):
    """Test that rising temperature during heating reduces offset."""
    setpoint, reason = policy.calculate_setpoint(
        mode=HVACMode.HEAT,
        room_temp=Temperature(19.0),  # 2°C below target
        target_temp=Temperature(21.0),
        temp_rate=0.5,  # Room warming at 0.5°C/hour - good
        context=base_context,
    )

    # Setpoint should be above target but moderated
    assert setpoint.value > 21.0
    assert setpoint.value < 28.0  # Should not be at max
```

### Приклад: Тестування Safety Policy

```python
"""test_safety.py"""
import pytest
from custom_components.smart_climate_controller.domain.policies.safety import (
    BasicSafetyPolicy,
)
from custom_components.smart_climate_controller.domain.value_objects import (
    Temperature,
)


@pytest.fixture
def safety_policy():
    return BasicSafetyPolicy()


def test_emergency_stop_when_too_hot(safety_policy, base_context):
    """Test emergency stop when room exceeds max temperature."""
    # Set room temp above max
    context = base_context
    snapshot = context.sensor_snapshot
    new_snapshot = snapshot.__class__(
        **{**snapshot.__dict__, 'room_temperature': Temperature(32.0)}
    )
    context = context.__class__(
        **{**context.__dict__, 'sensor_snapshot': new_snapshot}
    )

    should_stop, reason = safety_policy.should_emergency_stop(context)

    assert should_stop is True
    assert "above maximum" in reason.lower()


def test_no_stop_when_normal(safety_policy, base_context):
    """Test no emergency stop under normal conditions."""
    should_stop, reason = safety_policy.should_emergency_stop(base_context)

    assert should_stop is False
    assert "passed" in reason.lower()
```

## Тестування Application Layer

Application layer можна тестувати мокаючи infrastructure.

```python
"""test_controller.py"""
import pytest
from datetime import datetime

from custom_components.smart_climate_controller.application.controller import (
    ClimateController,
)


@pytest.fixture
def controller():
    return ClimateController()


def test_control_cycle_basic(controller):
    """Test basic control cycle execution."""
    command, decision = controller.execute_control_cycle(
        room_temp=23.0,
        outdoor_temp=20.0,
        device_hvac_mode="cool",
        device_setpoint=22.0,
        device_available=True,
        device_supported_modes=["off", "heat", "cool"],
        device_min_temp=16.0,
        device_max_temp=30.0,
        target_temp=21.0,
        min_room_temp=16.0,
        max_room_temp=30.0,
        deadband=0.5,
        base_offset=2.0,
        dynamic_rate_factor=10.0,
        max_dynamic_offset=5.0,
        outdoor_heat_threshold=12.0,
        outdoor_cool_threshold=18.0,
        mode_switch_hysteresis=1.0,
        min_mode_switch_interval=1800,
        min_command_interval=30,
        controller_enabled=True,
    )

    assert decision is not None
    # Room is 2°C above target, should want cooling
    assert decision.desired_mode.value in ["cool", "auto"]
```

## Інтеграційні тести з Home Assistant

Для повних інтеграційних тестів використовуйте pytest-homeassistant-custom-component:

```python
"""test_init.py"""
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.smart_climate_controller.const import DOMAIN


async def test_setup_entry(hass: HomeAssistant):
    """Test integration setup."""
    config = {
        "zone_name": "Test Zone",
        "climate_entity": "climate.test_ac",
        "room_temp_sensor": "sensor.room_temp",
        "outdoor_temp_sensor": "sensor.outdoor_temp",
        "target_temp": 21.0,
        # ... other config
    }

    # Would need to create mock entities first
    # Then test setup

    assert True  # Placeholder
```

## Ручне тестування

### Сценарій 1: Deadband behavior

1. Встановіть target_temp = 21.0, deadband = 0.5
2. Переконайтесь, що room_temp = 21.0
3. Спостерігайте атрибути entity
4. **Очікується**: Кондиціонер залишається в поточному режимі (не вимикається)

### Сценарій 2: Mode switch protection

1. Змініть outdoor_temp з 10°C (холодно) на 25°C (тепло)
2. Room потребує охолодження
3. **Очікується**: Режим не змінюється миттєво, є затримка min_mode_switch_interval

### Сценарій 3: Setpoint modulation

1. Встановіть room_temp = 24.0, target = 21.0
2. Спостерігайте sensor.desired_ac_setpoint
3. **Очікується**: Уставка знижується (наприклад, до 19°C для агресивного охолодження)
4. Коли room_temp наближається до target, уставка має наближатись до target

### Сценарій 4: Safety stop

1. Симулюйте room_temp > max_room_temp
2. **Очікується**: Кондиціонер вимикається, decision = "TURN_OFF", reason містить "SAFETY"

## Continuous Testing

Рекомендовано створити:
- Unit tests для всіх policies
- Integration tests для controller
- End-to-end tests з реальним HA test instance

```bash
# Run tests
pytest tests/

# With coverage
pytest --cov=custom_components.smart_climate_controller tests/
```

## Test Fixtures

Створіть `tests/conftest.py` з корисними fixtures:

```python
"""conftest.py"""
import pytest
from datetime import datetime

from custom_components.smart_climate_controller.domain.value_objects import *


@pytest.fixture
def mock_capabilities():
    return DeviceCapabilities(
        can_heat=True,
        can_cool=True,
        can_auto=True,
        can_dry=False,
        can_fan_only=False,
        min_setpoint=Temperature(16.0),
        max_setpoint=Temperature(30.0),
        supported_modes=frozenset([HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]),
    )


@pytest.fixture
def mock_sensor_data():
    return {
        "room_temp": 21.0,
        "outdoor_temp": 15.0,
        "timestamp": datetime.now(),
    }
```

## Мінімальний тестовий набір для MVP

1. ✅ Mode selection in deadband preserves current mode
2. ✅ Mode selection respects outdoor temperature
3. ✅ Mode selection respects timing locks
4. ✅ Setpoint calculation adjusts for error
5. ✅ Setpoint calculation adjusts for rate
6. ✅ Safety policy triggers on limits
7. ✅ Decision engine combines policies correctly
8. ✅ Controller executes full cycle
9. ✅ Commands are throttled correctly
10. ✅ Temperature rate is calculated from history
