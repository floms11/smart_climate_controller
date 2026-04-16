# Детальна інструкція встановлення та налаштування

## Передумови

### Необхідні entity в Home Assistant

Перед встановленням переконайтесь, що у вас є:

1. **Climate entity** — ваш кондиціонер
   - Приклад: `climate.bedroom_ac`
   - Має підтримувати режими `heat` та/або `cool`
   - Має можливість встановлення температури

2. **Sensor температури кімнати**
   - Приклад: `sensor.bedroom_temperature`
   - Device class: `temperature`
   - Оновлюється регулярно (мінімум раз на 5 хвилин)

3. **Sensor зовнішньої температури**
   - Приклад: `sensor.outdoor_temperature`
   - Device class: `temperature`
   - Може бути від метеостанції, інтеграції погоди, або локального датчика

### Перевірте наявність entities

```bash
# В Home Assistant Developer Tools → States
# Знайдіть ваші entity та перевірте, що вони доступні
```

## Встановлення

### Крок 1: Копіювання файлів

#### Варіант A: З локальної директорії

```bash
# SSH до вашого Home Assistant
ssh root@homeassistant.local

# Перейдіть до директорії config
cd /config

# Створіть директорію custom_components, якщо не існує
mkdir -p custom_components

# Скопіюйте папку smart_climate_controller
cp -r /path/to/smart_climate_controller custom_components/
```

#### Варіант B: Через Samba/File Editor

1. Підключіться до Home Assistant через Samba або File Editor
2. Відкрийте папку `config`
3. Створіть папку `custom_components` (якщо не існує)
4. Скопіюйте всю папку `smart_climate_controller` до `custom_components/`

#### Варіант C: Через terminal add-on

```bash
cd /config/custom_components
git clone https://github.com/your-username/smart_climate_controller.git
```

### Крок 2: Перевірка структури

Переконайтесь, що структура виглядає так:

```
/config/
└── custom_components/
    └── smart_climate_controller/
        ├── __init__.py
        ├── manifest.json
        ├── const.py
        ├── config_flow.py
        ├── coordinator.py
        ├── climate.py
        ├── sensor.py
        ├── diagnostics.py
        ├── services.yaml
        ├── strings.json
        ├── translations/
        ├── domain/
        ├── application/
        └── infrastructure/
```

### Крок 3: Перезавантаження Home Assistant

1. Settings → System → Restart
2. Або через Developer Tools → YAML → Restart

Зачекайте 1-2 хвилини після перезавантаження.

## Налаштування інтеграції

### Крок 1: Додавання інтеграції

1. Перейдіть до **Settings** → **Devices & Services**
2. Натисніть **+ ADD INTEGRATION** (праворуч знизу)
3. У пошуку введіть `Smart Climate Controller`
4. Якщо не знайдено, очистіть кеш браузера та оновіть сторінку

### Крок 2: Базова конфігурація

Заповніть форму:

| Поле | Опис | Приклад |
|------|------|---------|
| **Zone Name** | Назва зони/кімнати | `Спальня` |
| **Climate Entity** | Entity вашого кондиціонера | `climate.bedroom_ac` |
| **Room Temperature Sensor** | Датчик температури кімнати | `sensor.bedroom_temperature` |
| **Outdoor Temperature Sensor** | Датчик зовнішньої температури | `sensor.outdoor_temperature` |
| **Target Temperature** | Бажана температура | `21.0` |

Натисніть **SUBMIT**

### Крок 3: Перевірка створення

Перейдіть до **Settings** → **Devices & Services** → **Smart Climate Controller**

Ви маєте побачити:
- 1 climate entity: `climate.smart_climate_controller_<zone_name>`
- 3 sensor entities:
  - `sensor.<zone>_outdoor_temperature`
  - `sensor.<zone>_desired_ac_setpoint`
  - `sensor.<zone>_control_decision`

## Базове тестування

### Тест 1: Перевірка стану

1. Перейдіть до **Developer Tools** → **States**
2. Знайдіть `climate.smart_climate_controller_<your_zone>`
3. Перевірте attributes:
   - `control_active`: має бути `true`
   - `outdoor_temp`: має відображати реальну температуру
   - `last_decision`: має з'явитись після першого циклу (~60 секунд)

### Тест 2: Встановлення температури

1. Відкрийте climate entity в UI
2. Змініть target temperature на іншу (наприклад, 22°C)
3. Зачекайте 1-2 хвилини
4. Перевірте атрибут `desired_setpoint` — він має відрізнятися від target

### Тест 3: Увімкнення/вимкнення

1. Перемкніть climate entity в режим `OFF`
2. Перевірте `control_active` — має стати `false`
3. Кондиціонер має залишитись у поточному стані (не змінюватись)
4. Перемкніть назад в `AUTO`
5. `control_active` має стати `true`, керування відновиться

## Додаткові налаштування

### Відкриття Options Flow

1. **Settings** → **Devices & Services**
2. Знайдіть **Smart Climate Controller**
3. Клік на назву інтеграції
4. Натисніть **CONFIGURE**

### Рекомендовані налаштування для початку

**Базові параметри** (залишити за замовчуванням):
- Deadband: `0.5°C`
- Base Offset: `2.0°C`

**Outdoor thresholds** (налаштувати під ваш клімат):

Для помірного клімату:
- Outdoor Heat Threshold: `12°C`
- Outdoor Cool Threshold: `18°C`

Для холодного клімату:
- Outdoor Heat Threshold: `5°C`
- Outdoor Cool Threshold: `15°C`

Для спекотного клімату:
- Outdoor Heat Threshold: `15°C`
- Outdoor Cool Threshold: `22°C`

**Mode switch protection**:
- Mode Switch Hysteresis: `1.0°C` (за замовчуванням)
- Min Mode Switch Interval: `1800s` (30 хв) — можна зменшити до `900s` (15 хв) для швидшої реакції

**Control timing**:
- Control Interval: `60s` — як часто виконується цикл керування

## Налаштування Dashboard

### Simple Thermostat Card

```yaml
type: thermostat
entity: climate.smart_climate_controller_bedroom
```

### Детальна картка з сенсорами

```yaml
type: vertical-stack
cards:
  - type: thermostat
    entity: climate.smart_climate_controller_bedroom
    features:
      - type: climate-hvac-modes
        hvac_modes:
          - auto
          - 'off'

  - type: entities
    entities:
      - entity: sensor.bedroom_outdoor_temperature
        name: Outdoor Temperature
      - entity: sensor.bedroom_desired_ac_setpoint
        name: AC Setpoint
      - entity: sensor.bedroom_control_decision
        name: Last Decision

  - type: attribute
    entity: climate.smart_climate_controller_bedroom
    attribute: last_decision_reason
    name: Decision Reason
```

### Графік температур

```yaml
type: history-graph
entities:
  - entity: sensor.bedroom_temperature
    name: Room
  - entity: sensor.bedroom_outdoor_temperature
    name: Outdoor
  - entity: sensor.bedroom_desired_ac_setpoint
    name: AC Setpoint
hours_to_show: 24
```

## Логування та діагностика

### Увімкнення debug логів

Додайте до `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.smart_climate_controller: debug
```

Перезавантажте HA, логи будуть в **Settings** → **System** → **Logs**

### Download diagnostics

1. **Settings** → **Devices & Services** → **Smart Climate Controller**
2. Клік на назву інтеграції
3. Три крапки (⋮) → **Download diagnostics**
4. Отримаєте JSON файл з повною інформацією

## Типові проблеми

### Інтеграція не з'являється в списку

**Рішення**:
1. Перевірте структуру папок
2. Перезавантажте HA
3. Очистіть кеш браузера (Ctrl+Shift+R)
4. Перевірте логи на помилки

### Sensor unavailable

**Причини**:
- Entity ID введений неправильно
- Sensor дійсно недоступний
- Sensor не має device_class: temperature

**Рішення**:
- Перевірте правильність entity_id
- Переконайтесь, що sensor доступний в States
- Якщо потрібно, змініть entity через config flow

### Кондиціонер не реагує на команди

**Перевірка**:
1. Перевірте атрибут `last_decision` — чи є команди
2. Перевірте атрибут `command_locked_until` — можливо throttling
3. Перевірте debug логи

**Можливі причини**:
- `min_command_interval` занадто великий
- Кондиціонер недоступний
- Команди не змінюють стан (те саме значення)

### Mode не змінюється

**Це нормально**, якщо:
- Не минув `min_mode_switch_interval`
- Outdoor temperature в neutral зоні
- Поточний режим адекватний ситуації

**Перевірте**:
- Атрибут `last_mode_change`
- Атрибут `mode_locked_until`
- `last_decision_reason` — там буде пояснення

## Розширене використання

### Автоматизація на ніч

```yaml
automation:
  - alias: "Climate: Night mode"
    trigger:
      - platform: time
        at: "22:00:00"
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.smart_climate_controller_bedroom
        data:
          temperature: 20

  - alias: "Climate: Morning mode"
    trigger:
      - platform: time
        at: "07:00:00"
    action:
      - service: climate.set_temperature
        target:
          entity_id: climate.smart_climate_controller_bedroom
        data:
          temperature: 21
```

### Зміна налаштувань через automation

На жаль, options не можна змінювати через сервіси (це обмеження HA).
Але можна:
- Створити кілька інтеграцій з різними налаштуваннями
- Вимикати/вмикати потрібну через automation

### Інтеграція з присутністю

```yaml
automation:
  - alias: "Climate: Eco mode when away"
    trigger:
      - platform: state
        entity_id: binary_sensor.someone_home
        to: 'off'
        for:
          minutes: 30
    action:
      - service: climate.turn_off
        target:
          entity_id: climate.smart_climate_controller_bedroom

  - alias: "Climate: Normal mode when home"
    trigger:
      - platform: state
        entity_id: binary_sensor.someone_home
        to: 'on'
    action:
      - service: climate.turn_on
        target:
          entity_id: climate.smart_climate_controller_bedroom
```

## Оновлення інтеграції

### При оновленні коду

1. Замініть файли в `custom_components/smart_climate_controller/`
2. Перезавантажте Home Assistant
3. Якщо є зміни в config — можливо потрібно видалити та створити заново інтеграцію

### Збереження налаштувань

Налаштування зберігаються в `.storage/core.config_entries`
При видаленні інтеграції вони втрачаються.

Зробіть backup перед великими змінами.

## Підтримка

Якщо виникли проблеми:
1. Перевірте логи (Settings → System → Logs)
2. Download diagnostics
3. Створіть issue на GitHub з логами та diagnostics

## Наступні кроки

Після успішного встановлення:
1. Спостерігайте за роботою кілька днів
2. Аналізуйте графіки температур
3. Налаштуйте параметри під ваші потреби
4. Додайте автоматизації для різних сценаріїв
5. Ознайомтесь з TESTING_GUIDE.md для розуміння логіки
