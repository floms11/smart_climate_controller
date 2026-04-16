# Керівництво по налаштуванню мультиспліт систем

Цей документ пояснює, як налаштувати і керувати мультиспліт системами за допомогою Smart Climate Controller.

## Що таке мультиспліт система?

**Мультиспліт система** — це кондиціонер, де один зовнішній блок (outdoor unit) обслуговує декілька внутрішніх блоків (indoor units) в різних приміщеннях.

### Ключове обмеження

Всі внутрішні блоки, підключені до одного зовнішнього блоку, **повинні працювати в одному режимі**:
- Або всі в режимі **HEAT** (обігрів)
- Або всі в режимі **COOL** (охолодження)
- Окремі блоки можна **вимкнути** (OFF), але не змінити їх режим незалежно від інших

## Як об'єднати кондиціонери в мультиспліт групу

### Метод 1: Через UI (рекомендовано)

#### Крок 1: Створіть інтеграції для кожної зони

1. Перейдіть до **Settings → Devices & Services**
2. Натисніть **"+ ADD INTEGRATION"**
3. Знайдіть **"Smart Climate Controller"**
4. Заповніть основні поля для першої зони:
   - **Zone Name**: наприклад, "Спальня"
   - **Climate Entity**: виберіть внутрішній блок для спальні
   - **Room Temperature Sensor**: датчик температури в спальні
   - **Outdoor Temperature Sensor**: датчик зовнішньої температури
   - **Target Temperature**: цільова температура для спальні
   - **Multi-Split Group** (ВАЖЛИВО!): введіть ідентифікатор групи, наприклад: `main_house`

#### Крок 2: Додайте інші зони до тієї ж групи

5. Повторіть кроки 2-4 для кожної зони (Вітальня, Кухня, тощо)
6. **Важливо**: Для всіх зон, що належать до однієї мультиспліт системи, вкажіть **однаковий ідентифікатор групи** в полі "Multi-Split Group"

#### Приклад для трьох приміщень:

**Зона 1 - Спальня:**
- Zone Name: `Спальня`
- Climate Entity: `climate.bedroom_ac`
- Multi-Split Group: `main_house` ← однаковий ідентифікатор

**Зона 2 - Вітальня:**
- Zone Name: `Вітальня`
- Climate Entity: `climate.living_room_ac`
- Multi-Split Group: `main_house` ← однаковий ідентифікатор

**Зона 3 - Кухня:**
- Zone Name: `Кухня`
- Climate Entity: `climate.kitchen_ac`
- Multi-Split Group: `main_house` ← однаковий ідентифікатор

### Метод 2: Через configuration.yaml

Якщо ви віддаєте перевагу YAML конфігурації:

```yaml
# configuration.yaml

smart_climate_controller:
  # Перша мультиспліт система (main_house)
  - zone_name: "Спальня"
    climate_entity: climate.bedroom_ac
    room_temp_sensor: sensor.bedroom_temperature
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 21.0
    multi_split_group: "main_house"

  - zone_name: "Вітальня"
    climate_entity: climate.living_room_ac
    room_temp_sensor: sensor.living_room_temperature
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 22.0
    multi_split_group: "main_house"

  - zone_name: "Кухня"
    climate_entity: climate.kitchen_ac
    room_temp_sensor: sensor.kitchen_temperature
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 20.0
    multi_split_group: "main_house"

  # Друга мультиспліт система (garage_system)
  - zone_name: "Гараж"
    climate_entity: climate.garage_ac
    room_temp_sensor: sensor.garage_temperature
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 18.0
    multi_split_group: "garage_system"

  - zone_name: "Майстерня"
    climate_entity: climate.workshop_ac
    room_temp_sensor: sensor.workshop_temperature
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 19.0
    multi_split_group: "garage_system"

  # Окрема одинична система (не в групі)
  - zone_name: "Офіс"
    climate_entity: climate.office_ac
    room_temp_sensor: sensor.office_temperature
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 21.5
    # Без multi_split_group - працює незалежно
```

## Декілька мультиспліт груп

Ви можете мати **декілька незалежних мультиспліт груп**, кожна з унікальним ідентифікатором:

### Приклад: Будинок з двома системами

**Система 1** - Основний будинок (3 внутрішні блоки):
- Ідентифікатор групи: `main_house`
- Зони: Спальня, Вітальня, Кухня

**Система 2** - Гостьовий будинок (2 внутрішні блоки):
- Ідентифікатор групи: `guest_house`
- Зони: Гостьова спальня, Гостьова вітальня

**Окрема система** - Гараж (1 блок, працює незалежно):
- Без `multi_split_group`
- Зона: Гараж

Кожна група буде керуватися **незалежно** від інших груп.

## Як працює координація режиму

### Автоматичний вибір режиму групи

Smart Climate Controller автоматично вибирає оптимальний режим для всієї групи на основі:

1. **Потреб всіх приміщень** - скільки зон потребують обігріву vs охолодження
2. **Рівня ургентності** - наскільки далеко температура від цільової у кожній зоні
3. **Зовнішніх умов** - холодно чи жарко на вулиці
4. **Правил безпеки** - пріоритет обігріву взимку, щоб не переохолодити приміщення

### Приклад роботи

**Ситуація:**
- Спальня: поточна 19°C, цільова 21°C → потребує обігріву (відхилення -2°C)
- Вітальня: поточна 23°C, цільова 22°C → потребує охолодження (відхилення +1°C)
- Кухня: поточна 21.5°C, цільова 21°C → у нормі (відхилення +0.5°C)
- Зовнішня температура: 8°C (холодно)

**Рішення системи:**
- 🏆 **Режим групи: HEAT** (обігрів)
- **Причина**: Спальня має більше відхилення (-2°C) і на вулиці холодно. Пріоритет безпеки - запобігти переохолодженню.

**Дії по зонах:**
- Спальня: **HEAT ON** - працює на обігрів
- Вітальня: **OFF** - вимкнена, бо їй потрібне охолодження, а група працює на обігрів
- Кухня: **HEAT ON** - працює з групою, хоч їй не дуже потрібно (невелике відхилення)

### Правила вибору режиму

1. **Пріоритет безпеки (зима)**:
   - Якщо на вулиці < 12°C (налаштовується) і є зони, що потребують обігріву
   - Обігрів має пріоритет, щоб не заморозити приміщення

2. **Пріоритет безпеки (літо)**:
   - Якщо на вулиці > 18°C (налаштовується) і є зони, що потребують охолодження
   - Охолодження має пріоритет, щоб не перегріти приміщення

3. **Голосування**:
   - Якщо більше зон потребують обігріву → HEAT
   - Якщо більше зон потребують охолодження → COOL

4. **Ургентність**:
   - При рівній кількості голосів - вибирається режим для зони з більшим відхиленням температури

5. **Зовнішні умови**:
   - Якщо все інше рівне - орієнтуємося на зовнішню температуру

## Індивідуальне керування зонами

### Коли блок працює з групою

Блок працює в режимі групи, якщо:
- Він потребує того ж режиму, що й група
- Відхилення температури невелике (< 2 × deadband)

### Коли блок вимикається

Блок автоматично вимикається (OFF), якщо:
- Група працює на HEAT, а йому потрібне COOL і відхилення > 1°C
- Група працює на COOL, а йому потрібен HEAT і відхилення > -1°C
- Температура в зоні вже в нормі

**Приклад:**
```
Група: HEAT (обігрів)
Спальня: 19°C (цільова 21°C) → HEAT ON (працює)
Вітальня: 25°C (цільова 22°C) → OFF (вимкнена, бо надто жарко)
```

## Діагностика мультиспліт групи

### Перевірка налаштування

Після створення інтеграцій перевірте, що зони правильно об'єдналися:

1. Перейдіть до **Developer Tools → States**
2. Знайдіть ваш climate entity, наприклад `climate.smart_climate_controller_bedroom`
3. Перегляньте **Attributes**:
   - `multi_split_group`: має містити ідентифікатор групи (наприклад, `main_house`)
   - `group_shared_mode`: поточний спільний режим групи (`heat`, `cool`, або `null`)

### Атрибути для діагностики

Кожна зона в мультиспліт групі має додаткові атрибути:

```yaml
multi_split_group: "main_house"           # ID групи
group_shared_mode: "heat"                 # Поточний режим всієї групи
last_decision_reason: "Zone aligned..."   # Причина рішення контролера
```

### Перегляд інформації про групу

У логах ви побачите:
```
[smart_climate_controller] Registered multi-split group: main_house
[smart_climate_controller] Multi-split group 'main_house' mode changed: None -> heat
[smart_climate_controller] Added zone Спальня to multi-split group main_house
```

## Поширені сценарії

### Сценарій 1: Одна система, три кімнати

```yaml
multi_split_group: "my_home"  # Для всіх трьох зон
```

Всі три кімнати будуть працювати в одному режимі.

### Сценарій 2: Два поверхи, дві системи

**Перший поверх:**
```yaml
multi_split_group: "floor_1"  # Для кімнат на першому поверсі
```

**Другий поверх:**
```yaml
multi_split_group: "floor_2"  # Для кімнат на другому поверсі
```

Кожен поверх керується незалежно.

### Сценарій 3: Основний будинок + гостьовий

**Основний будинок:**
```yaml
multi_split_group: "main_house"
```

**Гостьовий будинок:**
```yaml
multi_split_group: "guest_house"
```

Дві повністю незалежні системи.

### Сценарій 4: Мультиспліт + окремі блоки

**Мультиспліт система:**
```yaml
# Спальня, Вітальня, Кухня
multi_split_group: "main_system"
```

**Окремі блоки:**
```yaml
# Гараж, Офіс - без multi_split_group
# Працюють незалежно
```

## Зміна налаштувань групи

### Додати зону до існуючої групи

1. Створіть нову інтеграцію для зони
2. Вкажіть той самий `multi_split_group` ID
3. Зона автоматично приєднається до групи

### Видалити зону з групи

1. Перейдіть до **Settings → Devices & Services**
2. Знайдіть вашу інтеграцію Smart Climate Controller
3. Натисніть **CONFIGURE**
4. Очистіть поле **Multi-Split Group** (залиште порожнім)
5. Збережіть
6. Зона буде працювати незалежно

### Перемістити зону в іншу групу

1. Відкрийте **CONFIGURE** для зони
2. Змініть **Multi-Split Group** на новий ID
3. Збережіть
4. Зона переміститься в нову групу

## Поради та найкращі практики

### ✅ Рекомендації

1. **Використовуйте зрозумілі ID груп**:
   - Добре: `main_house`, `floor_1`, `guest_building`
   - Погано: `group1`, `msys`, `abc`

2. **Один outdoor sensor на групу**:
   - Всі зони в одній групі можуть використовувати один датчик зовнішньої температури

3. **Індивідуальні цільові температури**:
   - Кожна зона може мати свою цільову температуру
   - Система автоматично знайде оптимальний компроміс

4. **Deadband налаштування**:
   - Для мультиспліт систем рекомендується deadband 0.5-1.0°C
   - Це зменшує частоту конфліктів між зонами

### ⚠️ Чого уникати

1. **Не плутайте групи**:
   - Переконайтеся, що всі блоки однієї фізичної системи мають однаковий `multi_split_group`

2. **Не об'єднуйте різні системи**:
   - Якщо у вас два зовнішні блоки - це дві різні групи

3. **Не залишайте порожні ID**:
   - Якщо поле `multi_split_group` порожнє - зона працює незалежно

## Приклад повної конфігурації

```yaml
# Будинок з двома мультиспліт системами та одним окремим блоком

smart_climate_controller:
  # === СИСТЕМА 1: Основний будинок (3 блоки) ===
  - zone_name: "Головна спальня"
    climate_entity: climate.master_bedroom_ac
    room_temp_sensor: sensor.master_bedroom_temp
    outdoor_temp_sensor: sensor.outdoor_temp
    target_temp: 21.0
    multi_split_group: "main_house"

  - zone_name: "Дитяча кімната"
    climate_entity: climate.kids_room_ac
    room_temp_sensor: sensor.kids_room_temp
    outdoor_temp_sensor: sensor.outdoor_temp
    target_temp: 22.0
    multi_split_group: "main_house"

  - zone_name: "Вітальня"
    climate_entity: climate.living_room_ac
    room_temp_sensor: sensor.living_room_temp
    outdoor_temp_sensor: sensor.outdoor_temp
    target_temp: 21.5
    multi_split_group: "main_house"

  # === СИСТЕМА 2: Другий поверх (2 блоки) ===
  - zone_name: "Гостьова спальня"
    climate_entity: climate.guest_bedroom_ac
    room_temp_sensor: sensor.guest_bedroom_temp
    outdoor_temp_sensor: sensor.outdoor_temp
    target_temp: 20.0
    multi_split_group: "second_floor"

  - zone_name: "Кабінет"
    climate_entity: climate.office_ac
    room_temp_sensor: sensor.office_temp
    outdoor_temp_sensor: sensor.outdoor_temp
    target_temp: 21.0
    multi_split_group: "second_floor"

  # === ОКРЕМА СИСТЕМА: Гараж (1 блок, працює незалежно) ===
  - zone_name: "Гараж"
    climate_entity: climate.garage_ac
    room_temp_sensor: sensor.garage_temp
    outdoor_temp_sensor: sensor.outdoor_temp
    target_temp: 15.0
    # Без multi_split_group - працює незалежно
```

**Результат:**
- **Група `main_house`**: 3 зони, працюють разом в одному режимі
- **Група `second_floor`**: 2 зони, працюють разом в одному режимі
- **Гараж**: працює незалежно, може бути в будь-якому режимі

## Підтримка

Якщо у вас виникли питання або проблеми з налаштуванням мультиспліт систем:

- 📖 Читайте основний [README.md](README.md)
- 🐛 Створіть [issue на GitHub](https://github.com/floms/smart_climate_controller/issues)
- 💬 Обговорюйте в Home Assistant Community

---

**Версія документа**: 0.2.0
**Остання актуалізація**: 2026-04-16
