# Smart Climate Controller

Розумна кастомна інтеграція Home Assistant для керування кліматичними системами з акцентом на безперервну модуляцію уставки замість on/off циклів.

## Особливості

### Поточна версія (MVP)

- **Continuous Setpoint Control**: Основний механізм — модуляція уставки кондиціонера, а не увімкнення/вимкнення
- **Outdoor-Aware Mode Selection**: Автоматичний вибір режиму нагріву/охолодження з урахуванням зовнішньої температури
- **Intelligent Deadband**: Зона стабілізації, де пристрій залишається увімкненим без агресивних змін
- **Mode Switch Protection**: Захист від частих перемикань режиму через hysteresis та мінімальні інтервали
- **Temperature Rate Tracking**: Відстеження швидкості зміни температури для прогнозування
- **Safety Limits**: Аварійне вимкнення при досягненні критичних температур

### Чиста архітектура

Інтеграція побудована з чіткою шаровою архітектурою:

```
Domain Layer (HA-agnostic)
    ├── Models & Value Objects
    ├── Policies (Mode Selection, Setpoint Adjustment, Safety)
    └── Decision Engine

Application Layer
    ├── Controller (orchestration)
    ├── Mapper (domain ↔ HA)
    └── Commands

Infrastructure Layer
    ├── HA State Reader
    ├── HA Command Sender
    └── Device Adapters

Presentation Layer
    └── Climate Entity, Sensors
```

## Встановлення

### Метод 1: HACS (рекомендовано)

1. Відкрийте HACS в Home Assistant
2. Натисніть "Integrations"
3. Натисніть три крапки вгорі справа → "Custom repositories"
4. Додайте `https://github.com/floms/smart_climate_controller` та виберіть категорію "Integration"
5. Знайдіть "Smart Climate Controller" та натисніть "Install"
6. Перезавантажте Home Assistant

### Метод 2: Вручну

1. Завантажте останню версію з [Releases](https://github.com/floms/smart_climate_controller/releases)
2. Розархівуйте та скопіюйте папку `custom_components/smart_climate_controller` до вашої конфігурації HA:

```bash
cd /config
mkdir -p custom_components
# Скопіюйте папку smart_climate_controller сюди
```

3. Структура має бути:
```
/config/custom_components/smart_climate_controller/
    ├── __init__.py
    ├── manifest.json
    ├── ...
```

4. Перезавантажте Home Assistant

## Налаштування

### Початкове налаштування

1. Перейдіть до Settings → Devices & Services
2. Натисніть "+ ADD INTEGRATION"
3. Знайдіть "Smart Climate Controller"
4. Введіть:
   - **Zone Name**: Назва зони (наприклад, "Спальня")
   - **Climate Device**: Ваш кондиціонер (climate entity)
   - **Room Temperature Sensor**: Датчик температури в кімнаті
   - **Outdoor Temperature Sensor**: Датчик зовнішньої температури
   - **Target Temperature**: Цільова температура (наприклад, 21°C)

### Додаткові параметри

Після створення інтеграції, натисніть "CONFIGURE" для налаштування:

#### Температурні межі
- **Deadband**: Зона стабілізації навколо цільової температури (за замовчуванням: 0.5°C)
- **Min/Max Room Temp**: Аварійні межі температури кімнати

#### Керування уставкою
- **Base Offset**: Базовий зсув уставки кондиціонера від цільової температури (за замовчуванням: 2.0°C)

#### Вибір режиму
- **Outdoor Heat Threshold**: Нижче цієї температури пріоритет — нагрів (за замовчуванням: 12°C)
- **Outdoor Cool Threshold**: Вище цієї температури пріоритет — охолодження (за замовчуванням: 18°C)
- **Mode Switch Hysteresis**: Гістерезис для запобігання осциляціям (за замовчуванням: 1.0°C)
- **Min Mode Switch Interval**: Мінімальний час між зміною режимів (за замовчуванням: 1800с = 30 хв)

#### Таймінги
- **Control Interval**: Інтервал циклу керування (за замовчуванням: 60с)

## Використання

### Entity

Після налаштування з'явиться climate entity:
- **Domain**: `climate`
- **Entity ID**: `climate.smart_climate_controller_<zone_name>`

Entity підтримує:
- Читання поточної температури
- Встановлення цільової температури
- Увімкнення/вимкнення контролера (режим AUTO/OFF)

### Sensors

Також створюються додаткові сенсори:
- `sensor.<zone>_outdoor_temperature`: Зовнішня температура
- `sensor.<zone>_desired_ac_setpoint`: Розрахована уставка для кондиціонера
- `sensor.<zone>_control_decision`: Останнє рішення контролера

### Attributes

Climate entity має багато корисних атрибутів для діагностики:
- `control_active`: Чи активний контролер
- `outdoor_temp`: Зовнішня температура
- `last_decision`: Тип останнього рішення
- `last_decision_reason`: Причина рішення
- `desired_mode`: Бажаний режим HVAC
- `desired_setpoint`: Бажана уставка
- `last_control_time`: Час останнього циклу
- `last_mode_change`: Час останньої зміни режиму

### Services

Доступні додаткові сервіси:

```yaml
# Встановити цільову температуру
service: smart_climate_controller.set_target_temperature
data:
  entry_id: "your_entry_id"
  temperature: 22.5

# Примусовий цикл керування
service: smart_climate_controller.force_update
data:
  entry_id: "your_entry_id"
```

## Приклади використання

### Автоматизація на основі присутності

```yaml
automation:
  - alias: "Climate: Away mode"
    trigger:
      - platform: state
        entity_id: binary_sensor.home_occupied
        to: 'off'
        for:
          minutes: 30
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.smart_climate_controller_bedroom
        data:
          temperature: 19

  - alias: "Climate: Home mode"
    trigger:
      - platform: state
        entity_id: binary_sensor.home_occupied
        to: 'on'
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.smart_climate_controller_bedroom
        data:
          temperature: 21
```

### Dashboard Card

```yaml
type: thermostat
entity: climate.smart_climate_controller_bedroom
features:
  - type: climate-hvac-modes
    hvac_modes:
      - auto
      - 'off'
```

## Як це працює

### Основна логіка

1. **Збір даних**: Кожні N секунд (control_interval) читає температуру кімнати, зовнішню температуру, стан кондиціонера

2. **Вибір режиму**: На основі:
   - Відхилення кімнатної температури від цільової
   - Зовнішньої температури
   - Поточного режиму
   - Часу з останньої зміни режиму

   Визначає потрібний режим: HEAT, COOL, або OFF (лише в аварійних випадках)

3. **Розрахунок уставки**: Обчислює оптимальну уставку для кондиціонера:
   - Base offset: фіксований зсув від цільової температури
   - Error-based offset: додатковий зсув залежно від величини відхилення
   - Rate-based offset: корекція на основі швидкості зміни температури

4. **Захисні перевірки**: Перевіряє температурні межі, стан датчиків, таймінги

5. **Виконання команди**: Якщо є зміни і дозволено за таймінгами — відправляє команду кондиціонеру

### Ключова відмінність від звичайного термостата

**Звичайний термостат**:
- Температура < target → включити нагрів
- Температура > target → включити охолодження
- Температура в deadband → ВИМКНУТИ

**Smart Climate Controller**:
- Температура < target → перевірити outdoor, можливо heating, скоригувати setpoint
- Температура > target → перевірити outdoor, можливо cooling, скоригувати setpoint
- Температура в deadband → **ЗБЕРЕГТИ поточний режим**, плавно утримувати setpoint
- Вимкнення — лише в критичних ситуаціях

## Діагностика

### Логування

Увімкніть debug логування в `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.smart_climate_controller: debug
```

### Diagnostics

Перейдіть до інтеграції → три крапки → "Download diagnostics"

Отримаєте JSON з повною інформацією про стан, рішення, історію.

## Майбутні розширення

Архітектура готова до:

### Multi-Device Zones
- Кондиціонер + рекуператор в одній зоні
- Координація між пристроями
- Пріоритети та обмеження

### Multi-Split Systems
- Один зовнішній блок, кілька внутрішніх
- Узгоджений режим
- Розподіл навантаження

### Ventilation & Recuperation
- Керування швидкістю вентилятора
- Режими за CO₂ та вологістю
- Байпас
- Нічний режим

### Multi-Zone Orchestration
- Кілька кімнат
- Глобальний координатор
- Міжзональний балансування

### Policy System
- Comfort policy
- Eco policy
- Sleep mode
- Away mode
- Anti-freeze
- Custom policies

## Розширення до Multi-Split

Для додавання підтримки мультиспліт-систем:

1. **Domain Layer**:
   - Додати `MultiSplitCoordinator` у `domain/services/coordination.py`
   - Реалізувати `SharedCapabilitiesPolicy` для узгодження режиму

2. **Infrastructure**:
   - Створити `MultiSplitAdapter` у `infrastructure/device_adapters/`
   - Адаптер керує всіма внутрішніми блоками як групою

3. **Application**:
   - Розширити `ClimateController` для роботи з групами пристроїв
   - Додати `DeviceGroupCommand` у `commands.py`

4. **Config Flow**:
   - Додати крок вибору типу системи (single / multi-split)
   - Для multi-split: вибір кількох внутрішніх блоків

## Розширення до Recuperator

Для додавання рекуператора:

1. **Domain Layer**:
   - Створити `RecuperatorPolicy` у `domain/policies/`
   - Додати `VentilationMode` до value objects

2. **Infrastructure**:
   - Створити `RecuperatorAdapter` у `device_adapters/`
   - Реалізувати методи `set_fan_speed`, `set_bypass_mode`

3. **Application**:
   - Додати `RecuperatorCommand` у `commands.py`
   - Розширити `ClimateController` для керування вентиляцією

4. **Sensors**:
   - Додати підтримку CO₂ sensor
   - Додати humidity sensor
   - Використовувати в decision engine

## Підтримка

- GitHub Issues: [створіть issue](https://github.com/floms/smart_climate_controller/issues)
- Документація: цей README
- Home Assistant Community: пошукайте за "Smart Climate Controller"

## Ліцензія

MIT License

## Розробник

@floms

---

**Версія**: 0.1.0 (MVP)
