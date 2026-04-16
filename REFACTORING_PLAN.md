# План рефакторингу Smart Climate Controller

## Огляд змін

Цей документ описує покроковий план повного рефакторингу інтеграції відповідно до нової логіки керування.

## Ключові зміни

### 1. Нова логіка setpoint adjustment (замість overshooting)

**Що видалити:**
- Всю логіку overshooting detection з `setpoint_adjustment.py` (lines 51-84)
- `base_offset`, `dynamic_rate_factor`, `max_dynamic_offset` з параметрів

**Що додати:**
- Ітеративну логіку: поточний setpoint AC + динаміка → коригування на ±1°C
- Якщо динаміка відсутня протягом `setpoint_adjustment_interval` (2 хв), змінити setpoint на `setpoint_step` (1°C) в потрібному напрямку
- Якщо динаміка є і правильна, не міняти setpoint
- Враховувати температуру на вулиці для розуміння "природного" напрямку зміни

### 2. Розумне перемикання режимів

**Що змінити в `mode_selection.py`:**
- Перед перемиканням COOL↔HEAT перевіряти, чи можна досягти цілі корекцією setpoint у поточному режимі
- Приклад: якщо COOL активний, але треба нагріти на 0.5°C, і на вулиці жарко - спробувати підвищити setpoint AC замість перемикання на HEAT
- Перемикати режим тільки якщо:
  - Потрібна велика зміна температури (більше ніж може дати корекція setpoint)
  - Корекція setpoint у поточному режимі не дає результату протягом тривалого часу
  - Температура на вулиці підтверджує необхідність іншого режиму

### 3. Антифлапінг - мінімальні часи

**Додати відстеження стану для кожного AC:**
- `last_run_start`: коли AC увімкнувся (перейшов з OFF в HEAT/COOL)
- `last_idle_start`: коли AC вимкнувся (перейшов в OFF з HEAT/COOL)

**Перевірки перед командами:**
- Якщо AC працює (HEAT/COOL), не дозволяти вимкнення, якщо пройшло менше `min_run_time` (5 хв)
- Якщо AC вимкнений (OFF), не дозволяти увімкнення, якщо пройшло менше `min_idle_time` (3 хв)
- Ці перевірки - для кожного AC окремо, не для групи

### 4. Температурна динаміка

**Додати до coordinator:**
- `TemperatureTracker` instance для кожної зони
- Викликати `tracker.add_measurement(room_temp, now)` на кожному циклі
- Передавати `short_term_rate` (1 хв) та `long_term_rate` (10 хв) в decision engine

**Використання динаміки:**
- **Short-term (1 хв)**: показує миттєву реакцію AC, використовується для перевірки "чи працює поточний setpoint"
- **Long-term (10 хв)**: показує загальний тренд, використовується для рішень про перемикання режиму
- Якщо short-term динаміка правильна (температура йде до цілі), не коригувати setpoint
- Якщо short-term динаміка відсутня або не в ту сторону → коригувати setpoint

### 5. Синхронізація груп при ручних змінах

**Поточна логіка (неправильна):**
```python
# В coordinator.py lines 303-336: відновлює режим назад
if desired_mode and new_mode != desired_mode:
    # Restore mode back
```

**Нова логіка (правильна):**
```python
# Якщо зміна на фізичному кондиціонері (не через термостат):
if mode_changed_on_device:
    # Відновити режим назад на цьому кондиціонері
    restore_mode_on_device(climate_entity, desired_mode)

# Якщо зміна через термостат інтеграції:
if mode_changed_on_thermostat:
    # Синхронізувати всю групу на новий режим
    sync_group_to_new_mode(group_id, new_mode)
```

**Як відрізнити:**
- Зміна через термостат: `climate.py` → `async_set_hvac_mode()` → встановлює `manual_mode_override`
- Зміна на пристрої: state listener бачить зміну, але `manual_mode_override` не змінювався

### 6. Умови вимкнення/увімкнення

**Вимкнення (HEAT/COOL → OFF):**
- HEAT: якщо `room_temp > target_temp + deadband` і пройшов `min_run_time`
- COOL: якщо `room_temp < target_temp - deadband` і пройшов `min_run_time`

**Увімкнення (OFF → HEAT/COOL):**
- Якщо `abs(room_temp - target_temp) > deadband` і пройшов `min_idle_time`
- Режим обирається за звичайною логікою `mode_selection`

## Покрокова реалізація

### Крок 1: Оновити value_objects.py

Додати нові поля до `ControlContext`:

```python
@dataclass(frozen=True)
class ControlContext:
    # ... existing fields ...

    # Temperature dynamics
    short_term_rate: Optional[float] = None  # °C/hour over 1 minute
    long_term_rate: Optional[float] = None   # °C/hour over 10 minutes

    # Anti-flapping timestamps
    last_run_start: Optional[datetime] = None
    last_idle_start: Optional[datetime] = None

    # New timing constraints
    min_run_time: int = 300  # seconds
    min_idle_time: int = 180  # seconds
    setpoint_adjustment_interval: int = 120  # seconds
    setpoint_step: float = 1.0  # degrees

    # Track last setpoint adjustment
    last_setpoint_adjustment: Optional[datetime] = None
```

### Крок 2: Переписати setpoint_adjustment.py

Повністю замінити `DynamicSetpointAdjustmentPolicy.calculate_setpoint()`:

```python
def calculate_setpoint(
    self,
    mode: HVACMode,
    room_temp: Temperature,
    target_temp: Temperature,
    temp_rate: Optional[float],  # This is short_term_rate
    context: ControlContext,
) -> tuple[Temperature, str]:
    """
    Calculate setpoint using iterative adjustment logic.

    Key principle: adjust setpoint by small steps (1°C) and observe dynamics.
    Only adjust if dynamics are insufficient.
    """

    if mode == HVACMode.OFF:
        return target_temp, "Device off"

    if mode not in (HVACMode.HEAT, HVACMode.COOL):
        return target_temp, f"Unsupported mode {mode.value}"

    # Current setpoint on AC device
    current_setpoint = context.device_state.current_setpoint.value

    # Temperature error
    temp_error = float(room_temp - target_temp)

    # Determine desired direction
    # COOL: want temp to decrease (negative dynamics)
    # HEAT: want temp to increase (positive dynamics)
    if mode == HVACMode.COOL:
        desired_direction = -1  # temperature should go down
    else:  # HVACMode.HEAT
        desired_direction = 1   # temperature should go up

    # Check if we have good dynamics already
    has_good_dynamics = False
    if temp_rate is not None:
        # For COOL: good if temp is decreasing AND we need cooling
        # For HEAT: good if temp is increasing AND we need heating
        if mode == HVACMode.COOL and temp_error > context.deadband:
            has_good_dynamics = temp_rate < -0.5  # cooling at least 0.5°C/h
        elif mode == HVACMode.HEAT and temp_error < -context.deadband:
            has_good_dynamics = temp_rate > 0.5   # heating at least 0.5°C/h

    # If we have good dynamics, keep current setpoint
    if has_good_dynamics:
        return Temperature(current_setpoint), f"Good dynamics ({temp_rate:.1f}°C/h), keeping setpoint"

    # Check if enough time passed since last adjustment
    time_since_adjustment = None
    if context.last_setpoint_adjustment:
        time_since_adjustment = (context.now - context.last_setpoint_adjustment).total_seconds()

    # Don't adjust too frequently
    if time_since_adjustment is not None and time_since_adjustment < context.setpoint_adjustment_interval:
        return Temperature(current_setpoint), \
               f"Wait {context.setpoint_adjustment_interval - time_since_adjustment:.0f}s before next adjustment"

    # Need to adjust setpoint
    # Direction depends on mode and temperature error
    if mode == HVACMode.COOL:
        # Cooling: if too hot, make setpoint colder (decrease)
        if temp_error > context.deadband:
            new_setpoint = current_setpoint - context.setpoint_step
            reason = f"Too hot (+{temp_error:.1f}°C), decrease setpoint by {context.setpoint_step}°C"
        else:
            # Close to target or overshooting, increase setpoint
            new_setpoint = current_setpoint + context.setpoint_step
            reason = f"Near target or overshoot, increase setpoint by {context.setpoint_step}°C"
    else:  # HVACMode.HEAT
        # Heating: if too cold, make setpoint warmer (increase)
        if temp_error < -context.deadband:
            new_setpoint = current_setpoint + context.setpoint_step
            reason = f"Too cold ({temp_error:.1f}°C), increase setpoint by {context.setpoint_step}°C"
        else:
            # Close to target or overshooting, decrease setpoint
            new_setpoint = current_setpoint - context.setpoint_step
            reason = f"Near target or overshoot, decrease setpoint by {context.setpoint_step}°C"

    # Consider outdoor temperature for natural drift
    outdoor_temp = context.sensor_snapshot.outdoor_temperature.value

    # If outdoor naturally pushes temperature in desired direction, be less aggressive
    if mode == HVACMode.COOL and outdoor_temp < target_temp.value - 2:
        # Outdoor is cool, house will naturally cool down
        new_setpoint = min(new_setpoint + 0.5, current_setpoint)  # Be less aggressive
        reason += " | Outdoor cool, reduced adjustment"
    elif mode == HVACMode.HEAT and outdoor_temp > target_temp.value + 2:
        # Outdoor is warm, house will naturally warm up
        new_setpoint = max(new_setpoint - 0.5, current_setpoint)  # Be less aggressive
        reason += " | Outdoor warm, reduced adjustment"

    # Clamp to device limits
    new_setpoint = max(
        context.device_capabilities.min_setpoint.value,
        min(new_setpoint, context.device_capabilities.max_setpoint.value)
    )

    return Temperature(new_setpoint), reason
```

### Крок 3: Оновити mode_selection.py

Додати логіку "спробувати setpoint корекцію перед перемиканням":

```python
def select_mode(
    self,
    current_mode: HVACMode,
    room_temp: Temperature,
    target_temp: Temperature,
    outdoor_temp: Temperature,
    context: ControlContext,
) -> tuple[HVACMode, str]:
    """Select HVAC mode with intelligent mode switching."""

    # ... existing checks (controller_enabled, manual_override, timing lock) ...

    temp_error = float(room_temp - target_temp)

    # Check if in deadband
    in_deadband = abs(temp_error) <= context.deadband

    if in_deadband:
        # Stay in current mode if reasonable
        return current_mode, "In deadband, maintaining current mode"

    # Determine what we need
    needs_cooling = temp_error > context.deadband
    needs_heating = temp_error < -context.deadband

    # SMART SWITCHING: Try setpoint correction before mode switch

    if current_mode == HVACMode.COOL and needs_heating:
        # Currently cooling but need heating

        # Check if heating need is small
        if abs(temp_error) < 1.0:  # Less than 1°C difference
            # Check outdoor temperature
            if outdoor_temp.value > 20:  # Outdoor is warm
                # Small heating need + warm outdoor = try increasing AC setpoint first
                # Don't switch mode yet, let setpoint adjustment handle it
                return HVACMode.COOL, \
                       f"Small heating need ({temp_error:.1f}°C), outdoor warm, " \
                       "trying setpoint adjustment before mode switch"

        # Large heating need or setpoint correction failed (check long-term dynamics)
        if context.long_term_rate is not None and context.long_term_rate > -0.2:
            # Temperature not cooling significantly = correction attempts aren't working
            if context.device_capabilities.can_heat:
                return HVACMode.HEAT, \
                       f"Cooling not helping, switching to HEAT (error={temp_error:.1f}°C)"

        # Default: switch to heating
        if context.device_capabilities.can_heat:
            return HVACMode.HEAT, f"Heating needed (error={temp_error:.1f}°C)"

    elif current_mode == HVACMode.HEAT and needs_cooling:
        # Currently heating but need cooling

        # Check if cooling need is small
        if abs(temp_error) < 1.0:  # Less than 1°C difference
            # Check outdoor temperature
            if outdoor_temp.value < 15:  # Outdoor is cold
                # Small cooling need + cold outdoor = try decreasing AC setpoint first
                return HVACMode.HEAT, \
                       f"Small cooling need ({temp_error:.1f}°C), outdoor cold, " \
                       "trying setpoint adjustment before mode switch"

        # Large cooling need or setpoint correction failed
        if context.long_term_rate is not None and context.long_term_rate < 0.2:
            # Temperature not heating significantly = correction attempts aren't working
            if context.device_capabilities.can_cool:
                return HVACMode.COOL, \
                       f"Heating not helping, switching to COOL (error={temp_error:.1f}°C)"

        # Default: switch to cooling
        if context.device_capabilities.can_cool:
            return HVACMode.COOL, f"Cooling needed (error={temp_error:.1f}°C)"

    # Already in correct mode
    if needs_cooling and current_mode == HVACMode.COOL:
        return HVACMode.COOL, f"Continue cooling (error={temp_error:.1f}°C)"

    if needs_heating and current_mode == HVACMode.HEAT:
        return HVACMode.HEAT, f"Continue heating (error={temp_error:.1f}°C)"

    # Default: keep current mode
    return current_mode, "No mode change needed"
```

### Крок 4: Додати антифлапінг в decision_engine.py

Додати перевірки перед `_should_send_command()`:

```python
def _can_turn_off(self, context: ControlContext) -> tuple[bool, str]:
    """Check if AC can be turned off (respecting min_run_time)."""
    if context.last_run_start is None:
        return True, "No run time restriction"

    elapsed = (context.now - context.last_run_start).total_seconds()
    if elapsed < context.min_run_time:
        remaining = context.min_run_time - elapsed
        return False, f"Min run time not met, {remaining:.0f}s remaining"

    return True, "Min run time satisfied"

def _can_turn_on(self, context: ControlContext) -> tuple[bool, str]:
    """Check if AC can be turned on (respecting min_idle_time)."""
    if context.last_idle_start is None:
        return True, "No idle time restriction"

    elapsed = (context.now - context.last_idle_start).total_seconds()
    if elapsed < context.min_idle_time:
        remaining = context.min_idle_time - elapsed
        return False, f"Min idle time not met, {remaining:.0f}s remaining"

    return True, "Min idle time satisfied"

# In make_decision(), before returning TURN_OFF decision:
if desired_mode == HVACMode.OFF and current_mode != HVACMode.OFF:
    can_turn_off, reason = self._can_turn_off(context)
    if not can_turn_off:
        # Keep current mode
        return ControlDecision(
            decision_type=DecisionType.NO_ACTION,
            desired_mode=current_mode,
            desired_setpoint=context.device_state.current_setpoint,
            reason=f"Want to turn off but: {reason}",
            should_send_command=False,
            timestamp=context.now,
        )

# Before turning on:
if desired_mode in (HVACMode.HEAT, HVACMode.COOL) and current_mode == HVACMode.OFF:
    can_turn_on, reason = self._can_turn_on(context)
    if not can_turn_on:
        # Stay off
        return ControlDecision(
            decision_type=DecisionType.NO_ACTION,
            desired_mode=HVACMode.OFF,
            desired_setpoint=None,
            reason=f"Want to turn on but: {reason}",
            should_send_command=False,
            timestamp=context.now,
        )
```

### Крок 5: Оновити coordinator.py

**Додати:**
```python
from .infrastructure.temperature_tracker import TemperatureTracker

class SmartClimateCoordinator:
    def __init__(self, ...):
        # ... existing code ...

        # Temperature tracking for dynamics
        self.temp_tracker = TemperatureTracker()

        # Anti-flapping state
        self.last_run_start: Optional[datetime] = None
        self.last_idle_start: Optional[datetime] = None
        self.last_setpoint_adjustment: Optional[datetime] = None
```

**В `_async_update_data()`:**
```python
# Track temperature
self.temp_tracker.add_measurement(room_temp, datetime.now())

# Get dynamics
short_term_rate = self.temp_tracker.get_short_term_rate()
long_term_rate = self.temp_tracker.get_long_term_rate()

# Update anti-flapping timestamps
if device_mode in ("heat", "cool") and self.last_run_start is None:
    self.last_run_start = datetime.now()
elif device_mode == "off" and self.last_idle_start is None:
    self.last_idle_start = datetime.now()

# Pass to controller
command, decision = self.controller.execute_control_cycle(
    # ... existing params ...
    short_term_rate=short_term_rate,
    long_term_rate=long_term_rate,
    last_run_start=self.last_run_start,
    last_idle_start=self.last_idle_start,
    last_setpoint_adjustment=self.last_setpoint_adjustment,
    min_run_time=self.config["min_run_time"],
    min_idle_time=self.config["min_idle_time"],
    setpoint_adjustment_interval=self.config["setpoint_adjustment_interval"],
    setpoint_step=self.config["setpoint_step"],
)

# Update last_setpoint_adjustment if setpoint changed
if command and decision.decision_type == DecisionType.SET_SETPOINT:
    self.last_setpoint_adjustment = datetime.now()
```

### Крок 6: Переробити state listener

**Замінити логіку відновлення режиму на синхронізацію:**

```python
def _setup_state_listener(self):
    climate_entity = self.config.get("climate_entity")

    async def state_change_listener(event):
        if event.data.get("entity_id") != climate_entity:
            return

        new_state = event.data.get("new_state")
        old_state = event.data.get("old_state")

        if not new_state or not old_state:
            return

        new_mode = new_state.state
        old_mode = old_state.state

        if new_mode == old_mode:
            return

        # Check if this change came from thermostat or from device
        # If manual_mode_override was just set, this is from thermostat
        # Otherwise, this is from device

        # Get current desired mode from decision
        desired_mode = None
        if self.data and self.data.get("decision"):
            desired_mode = self.data.get("decision").desired_mode.value

        # CASE 1: Change from device (not through thermostat)
        # Restore mode back
        if new_mode != desired_mode and desired_mode:
            _LOGGER.warning(
                "Device mode changed to %s, but integration wants %s. Restoring...",
                new_mode, desired_mode
            )
            await asyncio.sleep(0.5)
            # Send command to restore
            from .application.commands import SetClimateCommand
            from .domain.value_objects import HVACMode, Temperature

            cmd = SetClimateCommand(
                device_id=climate_entity,
                hvac_mode=HVACMode(desired_mode),
                target_temperature=Temperature(self.config["target_temp"]),
            )
            await self.command_sender.send_climate_command(cmd, climate_entity)

        # CASE 2: Change from thermostat (manual_mode_override changed)
        # This is handled in climate.py async_set_hvac_mode()
        # which calls set_manual_mode() which syncs group

        # Update timestamps for anti-flapping
        if new_mode in ("heat", "cool") and old_mode == "off":
            self.last_run_start = datetime.now()
            self.last_idle_start = None
        elif new_mode == "off" and old_mode in ("heat", "cool"):
            self.last_idle_start = datetime.now()
            self.last_run_start = None

        # Trigger refresh
        self.hass.async_create_task(self.async_request_refresh())

    self.hass.bus.async_listen("state_changed", state_change_listener)
```

### Крок 7: Додати сенсори динаміки

В `sensor.py` додати нові сенсори:

```python
class ShortTermRateSensor(SmartClimateSensorBase):
    """Sensor showing short-term temperature change rate (1 minute)."""

    _attr_native_unit_of_measurement = "°C/h"
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    @property
    def native_value(self) -> Optional[float]:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("short_term_rate")

class LongTermRateSensor(SmartClimateSensorBase):
    """Sensor showing long-term temperature change rate (10 minutes)."""

    _attr_native_unit_of_measurement = "°C/h"
    _attr_device_class = SensorDeviceClass.TEMPERATURE

    @property
    def native_value(self) -> Optional[float]:
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get("long_term_rate")

# Add to async_setup_entry():
entities = [
    # ... existing ...
    ShortTermRateSensor(coordinator, entry),
    LongTermRateSensor(coordinator, entry),
]
```

### Крок 8: Оновити __init__.py для міграції

Додати нові параметри до defaults в async_setup_entry():

```python
defaults = {
    # ... existing ...
    "min_run_time": DEFAULT_MIN_RUN_TIME,
    "min_idle_time": DEFAULT_MIN_IDLE_TIME,
    "setpoint_adjustment_interval": DEFAULT_SETPOINT_ADJUSTMENT_INTERVAL,
    "setpoint_step": DEFAULT_SETPOINT_STEP,
}

# Remove old parameters that are no longer used
params_to_remove = ["base_offset", "dynamic_rate_factor", "max_dynamic_offset"]
for param in params_to_remove:
    if param in updated_data:
        del updated_data[param]
        needs_update = True
```

### Крок 9: Оновити config_flow.py

Видалити старі параметри, додати нові у options flow:

```python
# Remove these fields:
# - base_offset
# - dynamic_rate_factor
# - max_dynamic_offset

# Add these fields:
vol.Required(
    CONF_MIN_RUN_TIME,
    default=data.get(CONF_MIN_RUN_TIME, DEFAULT_MIN_RUN_TIME)
): NumberSelector(NumberSelectorConfig(min=60, max=1800, step=30, mode=NumberSelectorMode.BOX, unit_of_measurement="s")),

vol.Required(
    CONF_MIN_IDLE_TIME,
    default=data.get(CONF_MIN_IDLE_TIME, DEFAULT_MIN_IDLE_TIME)
): NumberSelector(NumberSelectorConfig(min=60, max=1800, step=30, mode=NumberSelectorMode.BOX, unit_of_measurement="s")),

vol.Required(
    CONF_SETPOINT_ADJUSTMENT_INTERVAL,
    default=data.get(CONF_SETPOINT_ADJUSTMENT_INTERVAL, DEFAULT_SETPOINT_ADJUSTMENT_INTERVAL)
): NumberSelector(NumberSelectorConfig(min=60, max=600, step=30, mode=NumberSelectorMode.BOX, unit_of_measurement="s")),

vol.Required(
    CONF_SETPOINT_STEP,
    default=data.get(CONF_SETPOINT_STEP, DEFAULT_SETPOINT_STEP)
): NumberSelector(NumberSelectorConfig(min=0.5, max=3.0, step=0.5, mode=NumberSelectorMode.BOX, unit_of_measurement="°C")),
```

## Тестування

Після кожного кроку тестувати:

1. **Ітеративна корекція setpoint**: встановити ціль 22°C при кімнатній 24°C, перевірити що setpoint знижується на 1°C кожні 2 хв
2. **Антифлапінг**: перевірити що AC не вимикається раніше ніж через 5 хв після увімкнення
3. **Синхронізація груп**: змінити режим на фізичному AC, перевірити що він повертається назад
4. **Синхронізація груп 2**: змінити режим на термостаті, перевірити що всі AC групи перемкнулись
5. **Розумне перемикання**: в COOL режимі при невеликому падінні температури перевірити що спочатку коригується setpoint, а не перемикається на HEAT

## Контрольний список файлів

- [x] `const.py` - додано нові параметри
- [x] `infrastructure/temperature_tracker.py` - створено
- [ ] `domain/value_objects.py` - оновити ControlContext
- [ ] `domain/policies/setpoint_adjustment.py` - повністю переписати
- [ ] `domain/policies/mode_selection.py` - додати розумне перемикання
- [ ] `domain/services/decision_engine.py` - додати антифлапінг
- [ ] `coordinator.py` - додати TemperatureTracker, переробити state listener
- [ ] `sensor.py` - додати сенсори динаміки
- [ ] `__init__.py` - оновити міграцію
- [ ] `config_flow.py` - оновити parameters
- [ ] `application/controller.py` - передавати нові параметри
- [ ] `application/mapper.py` - маппінг нових параметрів

## Примітки

- Всі часи в секундах для консистентності
- Температурна динаміка в °C/hour для читабельності
- Завжди використовувати `datetime.now()` для timestamp consistency
- Логувати всі рішення для налагодження
