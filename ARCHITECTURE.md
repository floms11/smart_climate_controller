# Архітектура Smart Climate Controller

## Огляд

Smart Climate Controller побудований на принципах **Clean Architecture** з чіткою шаровою структурою та розділенням відповідальності.

```
┌─────────────────────────────────────────────────────────────┐
│                  Presentation Layer                         │
│   (Home Assistant UI: climate entity, sensors, cards)       │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                 Infrastructure Layer                        │
│  ha_state.py, ha_commands.py, device_adapters/              │
│  (Adapters для читання HA state та відправки команд)        │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                 Application Layer                           │
│        controller.py, mapper.py, commands.py                │
│        (Orchestration, use cases, DTO mapping)              │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│                    Domain Layer                             │
│   models.py, value_objects.py, policies/, services/         │
│        (Pure business logic, HA-agnostic)                   │
└─────────────────────────────────────────────────────────────┘
```

## Шари детально

### 1. Domain Layer — Серце системи

**Розташування**: `domain/`

**Принцип**: Повна незалежність від Home Assistant, фреймворків, зовнішніх систем.

#### Компоненти:

**value_objects.py**
- `Temperature` — value object з валідацією
- `HVACMode` — enum режимів
- `SensorSnapshot` — знімок показань датчиків
- `DeviceState` — поточний стан пристрою
- `DeviceCapabilities` — можливості пристрою
- `ControlContext` — контекст для прийняття рішень
- `ControlDecision` — результат decision engine

**models.py**
- `ClimateDevice` — модель кліматичного пристрою
- `ClimateZone` — модель кліматичної зони

**policies/** — Стратегії прийняття рішень

Використовує **Strategy Pattern** для підміни алгоритмів:

- `base.py` — абстрактні інтерфейси policies
- `mode_selection.py` — `OutdoorAwareModeSelectionPolicy`
  - Логіка вибору HVAC режиму
  - Урахування outdoor temperature
  - Hysteresis та anti-oscillation
  - Mode switch timing protection

- `setpoint_adjustment.py` — `DynamicSetpointAdjustmentPolicy`
  - Розрахунок optimal setpoint
  - Base offset + error-based + rate-based
  - Плавна модуляція замість on/off

- `safety.py` — `BasicSafetyPolicy`
  - Перевірка температурних лімітів
  - Захист від небезпечних ситуацій
  - Emergency stop logic

**services/** — Domain services

- `decision_engine.py` — `ClimateDecisionEngine`
  - Orchestrates всі policies
  - Приймає `ControlContext`
  - Повертає `ControlDecision`
  - **Це мозок системи**

#### Чому це важливо:

✅ **Тестованість**: Domain logic тестується БЕЗ Home Assistant
✅ **Переносимість**: Можна використати з іншими системами (Domoticz, OpenHAB)
✅ **Ясність**: Бізнес-логіка не захаращена інфраструктурними деталями
✅ **Розширюваність**: Легко додати нові policies

---

### 2. Application Layer — Оркестрація

**Розташування**: `application/`

**Принцип**: Координує domain layer та infrastructure layer.

#### Компоненти:

**controller.py** — `ClimateController`

Головний use-case orchestrator:
- Збирає історію температур
- Обчислює temperature rate
- Будує `ControlContext` з різних джерел
- Викликає `DecisionEngine`
- Повертає команди для виконання
- Відстежує state (last_mode_change, last_command_sent)

**mapper.py** — `DomainMapper`

Перетворює між domain та HA representations:
- HA string `"cool"` ↔ Domain `HVACMode.COOL`
- Raw float values → Value Objects (`Temperature`)
- HA attributes → Domain models

**commands.py**

DTOs для команд:
- `SetClimateCommand`
- `SetTemperatureCommand`
- `SetModeCommand`

#### Потік даних:

```
1. Infrastructure читає HA state (raw values)
2. Application mapper перетворює на domain objects
3. Application controller викликає domain decision_engine
4. Domain повертає ControlDecision
5. Application будує Command
6. Infrastructure виконує Command через HA services
```

---

### 3. Infrastructure Layer — Зв'язок з Home Assistant

**Розташування**: `infrastructure/`

**Принцип**: Adapter Pattern для ізоляції від HA API.

#### Компоненти:

**ha_state.py** — `HAStateReader`

Читає стан з HA:
- `get_temperature(entity_id)` → float
- `get_climate_state(entity_id)` → dict
- Обробляє `STATE_UNAVAILABLE`, `STATE_UNKNOWN`

**ha_commands.py** — `HACommandSender`

Відправляє команди до HA:
- `send_climate_command(command, entity_id)`
- Викликає `climate.set_hvac_mode`, `climate.set_temperature`
- Логування, error handling

**device_adapters/** — Абстракція пристроїв

**base.py** — `ClimateDeviceAdapter`
- Абстрактний інтерфейс для різних типів пристроїв
- Визначає методи: `get_current_mode()`, `set_temperature()`, etc.

**climate_adapter.py** — `ClimateEntityAdapter`
- Реалізація для стандартних climate entities
- У майбутньому: `RecuperatorAdapter`, `MultiSplitAdapter`

#### Навіщо adapters:

✅ Легко додати підтримку нових типів пристроїв
✅ Domain layer не залежить від структури HA climate entity
✅ Можна mock'ати для тестування

---

### 4. Presentation Layer — HA Integration

**Розташування**: Кореневі файли інтеграції

#### Компоненти:

**`__init__.py`**
- `async_setup_entry()` — entry point
- Створює `SmartClimateCoordinator`
- Реєструє platforms
- Реєструє services

**coordinator.py** — `SmartClimateCoordinator`

Extends `DataUpdateCoordinator`:
- Керує control cycle timing
- Викликає `ClimateController.execute_control_cycle()`
- Відправляє команди через `HACommandSender`
- Зберігає результати для entities

**climate.py** — `SmartClimateEntity`

Climate entity representation:
- Extends `ClimateEntity`
- Читає дані з coordinator
- Відображає стан, атрибути
- Обробляє user commands (set_temperature, turn_on/off)

**sensor.py** — Debug sensors

- `OutdoorTemperatureSensor`
- `DesiredSetpointSensor`
- `ControlDecisionSensor`

**config_flow.py**

UI для конфігурації:
- `SmartClimateControllerConfigFlow` — початкова настройка
- `SmartClimateControllerOptionsFlow` — зміна параметрів

**diagnostics.py**

Diagnostics для Download Diagnostics feature.

---

## Ключові патерни

### Strategy Pattern

Policies є змінними стратегіями:

```python
class ModeSelectionPolicy(ABC):
    @abstractmethod
    def select_mode(...) -> HVACMode:
        pass

# Можна підставити різні реалізації:
OutdoorAwareModeSelectionPolicy()
SeasonalModeSelectionPolicy()  # future
AIBasedModeSelectionPolicy()    # future
```

### Dependency Injection

DecisionEngine отримує policies через конструктор:

```python
engine = ClimateDecisionEngine(
    mode_selection_policy=OutdoorAwareModeSelectionPolicy(),
    setpoint_policy=DynamicSetpointAdjustmentPolicy(),
    safety_policy=BasicSafetyPolicy(),
)
```

Легко замінити на інші або додати нові.

### Command Pattern

Команди є immutable DTOs:

```python
@dataclass(frozen=True)
class SetClimateCommand:
    device_id: str
    hvac_mode: HVACMode
    target_temperature: Optional[Temperature]
```

Розділяє "що зробити" від "як зробити".

### Value Objects

`Temperature`, `TemperatureRate` — value objects з валідацією:

```python
temp = Temperature(25.0)  # ✅
temp = Temperature(150.0) # ❌ ValueError
```

Забезпечує domain invariants.

---

## Потік даних — приклад

### Scenario: Control cycle execution

1. **Coordinator** (60s timer):
```python
await coordinator._async_update_data()
```

2. **Infrastructure читає state**:
```python
room_temp = state_reader.get_temperature("sensor.room_temp")
climate_state = state_reader.get_climate_state("climate.ac")
```

3. **Application викликає controller**:
```python
command, decision = controller.execute_control_cycle(
    room_temp=22.5,
    outdoor_temp=15.0,
    device_hvac_mode="cool",
    ...
)
```

4. **Controller будує context** (application layer):
```python
sensor_snapshot = DomainMapper.create_sensor_snapshot(...)
device_state = DomainMapper.create_device_state(...)
context = DomainMapper.create_control_context(...)
```

5. **Domain приймає рішення**:
```python
decision = decision_engine.make_decision(context)
```

6. **DecisionEngine orchestrates policies** (domain layer):
```python
# 1. Safety check
should_stop, reason = safety_policy.should_emergency_stop(context)

# 2. Mode selection
desired_mode, mode_reason = mode_selection_policy.select_mode(...)

# 3. Setpoint calculation
desired_setpoint, setpoint_reason = setpoint_policy.calculate_setpoint(...)

# 4. Build decision
decision = ControlDecision(
    decision_type=DecisionType.SET_MODE_AND_SETPOINT,
    desired_mode=HVACMode.COOL,
    desired_setpoint=Temperature(19.0),
    reason="...",
    should_send_command=True,
)
```

7. **Application будує command**:
```python
command = SetClimateCommand(
    device_id="climate.ac",
    hvac_mode=HVACMode.COOL,
    target_temperature=Temperature(19.0),
)
```

8. **Infrastructure виконує command**:
```python
await command_sender.send_climate_command(command, "climate.ac")
```

9. **HA викликає service**:
```python
await hass.services.async_call(
    "climate",
    "set_temperature",
    {
        "entity_id": "climate.ac",
        "hvac_mode": "cool",
        "temperature": 19.0,
    }
)
```

---

## Розширюваність

### Додати новий тип пристрою (рекуператор)

1. **Domain**: Додати `VentilationMode` enum, нові capabilities
2. **Infrastructure**: Створити `RecuperatorAdapter`
3. **Application**: Розширити `ClimateController` для підтримки ventilation commands
4. **Config Flow**: Додати вибір типу пристрою

**Не потрібно змінювати**: decision_engine, policies (або мінімально)

### Додати нову policy (Eco Mode)

1. **Domain**: Створити `EcoModePolicy` implements `ModeSelectionPolicy`
2. **Application**: Додати config option для вибору policy
3. **Controller**: Inject потрібну policy в DecisionEngine

**Не потрібно змінювати**: infrastructure, entities, coordinator

### Multi-device zone

1. **Domain**: `ClimateZone.devices` вже є list
2. **Application**: Розширити controller для ітерації по devices
3. **Domain**: Додати `DeviceCoordinationPolicy` для узгодження команд
4. **Infrastructure**: Команди на кілька пристроїв

---

## Переваги архітектури

### ✅ Тестованість

- Domain layer тестується без HA
- Application layer mock'ає infrastructure
- Integration tests з real HA test framework

### ✅ Незалежність від Home Assistant

Domain може працювати з будь-якою системою.
Достатньо написати нові adapters.

### ✅ Ясність

Кожен шар має одну відповідальність:
- Domain: бізнес-логіка
- Application: orchestration
- Infrastructure: IO
- Presentation: UI

### ✅ Розширюваність

Додавання features не ламає існуючий код.
Нові policies, нові adapters, нові entities — все працює.

### ✅ Maintainability

Зміни локалізовані:
- Змінити логіку вибору режиму → policy
- Додати новий пристрій → adapter
- Змінити UI → entity
- Змінити джерело даних → state reader

---

## Недоліки та компроміси

### ⚠️ Складність для простих випадків

Для керування одним кондиціонером це може здатися "overengineering".

**Відповідь**: Система розрахована на майбутнє масштабування. MVP — це фундамент.

### ⚠️ Більше коду

Більше файлів, більше класів, більше абстракцій.

**Відповідь**: Але кожен файл простий, зрозумілий, легко тестується.

### ⚠️ Крива навчання

Новому розробнику потрібен час, щоб розібратись у структурі.

**Відповідь**: Хороша документація (цей файл!) та чіткі boundaries допомагають.

---

## Порівняння з альтернативними підходами

### Підхід 1: Monolith у climate.py

**Все в одному файлі**:
```python
class SmartClimateEntity(ClimateEntity):
    async def async_update(self):
        # Read sensors
        # Calculate everything
        # Send commands
        # All in one method
```

**Проблеми**:
- ❌ Неможливо тестувати без HA
- ❌ Важко додати нові функції
- ❌ Логіка змішана з infrastructure
- ❌ Не масштабується

### Підхід 2: Helper functions

**Логіка в helper functions**:
```python
def calculate_setpoint(room_temp, target, ...):
    return setpoint

def select_mode(room_temp, outdoor, ...):
    return mode
```

**Проблеми**:
- ⚠️ Краще, ніж monolith
- ❌ Важко змінити стратегії
- ❌ Глобальний state
- ❌ Weak typing

### Підхід 3: Clean Architecture (наш)

**Переваги**:
- ✅ Тестується
- ✅ Масштабується
- ✅ Ясний
- ✅ Future-proof

**Компроміс**:
- ⚠️ Більше коду спочатку
- ✅ Менше проблем потім

---

## Висновок

Smart Climate Controller використовує **Clean Architecture** для забезпечення:
- Чистоти бізнес-логіки
- Незалежності від фреймворків
- Легкості тестування
- Можливості масштабування

Це **інвестиція в майбутнє**, а не швидкий hack для одного випадку.

Архітектура дозволяє розвивати систему від простого контролера одного AC до повноцінної системи керування мікрокліматом будинку.
