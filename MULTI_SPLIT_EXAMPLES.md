# Приклади налаштування мультиспліт систем

Швидкі приклади для різних сценаріїв використання.

## Приклад 1: Проста система - 3 кімнати

**Ситуація:** У вас один зовнішній блок і три внутрішні блоки (Спальня, Вітальня, Кухня).

### Налаштування через UI

1. **Settings → Devices & Services → Add Integration → Smart Climate Controller**

2. **Спальня:**
   - Zone Name: `Спальня`
   - Climate Entity: `climate.bedroom_ac`
   - Room Temp Sensor: `sensor.bedroom_temperature`
   - Outdoor Temp Sensor: `sensor.outdoor_temperature`
   - Target Temperature: `21.0`
   - **Multi-Split Group: `my_home`** ← Важливо!

3. **Вітальня:**
   - Zone Name: `Вітальня`
   - Climate Entity: `climate.living_room_ac`
   - Room Temp Sensor: `sensor.living_room_temperature`
   - Outdoor Temp Sensor: `sensor.outdoor_temperature`
   - Target Temperature: `22.0`
   - **Multi-Split Group: `my_home`** ← Той самий ID!

4. **Кухня:**
   - Zone Name: `Кухня`
   - Climate Entity: `climate.kitchen_ac`
   - Room Temp Sensor: `sensor.kitchen_temperature`
   - Outdoor Temp Sensor: `sensor.outdoor_temperature`
   - Target Temperature: `20.0`
   - **Multi-Split Group: `my_home`** ← Той самий ID!

### YAML конфігурація

```yaml
smart_climate_controller:
  - zone_name: "Спальня"
    climate_entity: climate.bedroom_ac
    room_temp_sensor: sensor.bedroom_temperature
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 21.0
    multi_split_group: "my_home"

  - zone_name: "Вітальня"
    climate_entity: climate.living_room_ac
    room_temp_sensor: sensor.living_room_temperature
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 22.0
    multi_split_group: "my_home"

  - zone_name: "Кухня"
    climate_entity: climate.kitchen_ac
    room_temp_sensor: sensor.kitchen_temperature
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 20.0
    multi_split_group: "my_home"
```

**Результат:** Всі три кімнати працюють в одному режимі (HEAT або COOL). Система автоматично вибирає оптимальний режим.

---

## Приклад 2: Два поверхи - дві системи

**Ситуація:** Будинок має два поверхи, кожен з окремою мультиспліт системою.

### Перший поверх (система 1)

```yaml
smart_climate_controller:
  - zone_name: "Вітальня"
    climate_entity: climate.floor1_living_ac
    room_temp_sensor: sensor.floor1_living_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 22.0
    multi_split_group: "floor_1"  # ← Група для першого поверху

  - zone_name: "Кухня"
    climate_entity: climate.floor1_kitchen_ac
    room_temp_sensor: sensor.floor1_kitchen_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 21.0
    multi_split_group: "floor_1"  # ← Та сама група
```

### Другий поверх (система 2)

```yaml
  - zone_name: "Головна спальня"
    climate_entity: climate.floor2_master_ac
    room_temp_sensor: sensor.floor2_master_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 21.0
    multi_split_group: "floor_2"  # ← Інша група для другого поверху

  - zone_name: "Дитяча"
    climate_entity: climate.floor2_kids_ac
    room_temp_sensor: sensor.floor2_kids_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 22.0
    multi_split_group: "floor_2"  # ← Та сама група

  - zone_name: "Гостьова"
    climate_entity: climate.floor2_guest_ac
    room_temp_sensor: sensor.floor2_guest_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 20.0
    multi_split_group: "floor_2"  # ← Та сама група
```

**Результат:**
- Перший поверх (2 зони) керується незалежно від другого
- Другий поверх (3 зони) має свою окрему систему керування

---

## Приклад 3: Мультиспліт + окремі блоки

**Ситуація:** Основна частина будинку на мультиспліт, а гараж і офіс - окремі блоки.

```yaml
smart_climate_controller:
  # === МУЛЬТИСПЛІТ ГРУПА (основний будинок) ===
  - zone_name: "Спальня"
    climate_entity: climate.bedroom_ac
    room_temp_sensor: sensor.bedroom_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 21.0
    multi_split_group: "main_house"  # ← В групі

  - zone_name: "Вітальня"
    climate_entity: climate.living_room_ac
    room_temp_sensor: sensor.living_room_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 22.0
    multi_split_group: "main_house"  # ← В групі

  - zone_name: "Кухня"
    climate_entity: climate.kitchen_ac
    room_temp_sensor: sensor.kitchen_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 20.5
    multi_split_group: "main_house"  # ← В групі

  # === ОКРЕМІ БЛОКИ (працюють незалежно) ===
  - zone_name: "Гараж"
    climate_entity: climate.garage_ac
    room_temp_sensor: sensor.garage_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 15.0
    # Без multi_split_group → працює незалежно

  - zone_name: "Офіс"
    climate_entity: climate.office_ac
    room_temp_sensor: sensor.office_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 21.0
    # Без multi_split_group → працює незалежно
```

**Результат:**
- Спальня, Вітальня, Кухня: працюють в одному режимі (група `main_house`)
- Гараж: незалежний, може бути в будь-якому режимі
- Офіс: незалежний, може бути в будь-якому режимі

---

## Приклад 4: Основний будинок + гостьовий будинок

**Ситуація:** Дві окремі будівлі, кожна з власною мультиспліт системою.

```yaml
smart_climate_controller:
  # === ОСНОВНИЙ БУДИНОК ===
  - zone_name: "Основна спальня"
    climate_entity: climate.main_master_bedroom_ac
    room_temp_sensor: sensor.main_master_bedroom_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 21.0
    multi_split_group: "main_building"

  - zone_name: "Основна вітальня"
    climate_entity: climate.main_living_room_ac
    room_temp_sensor: sensor.main_living_room_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 22.0
    multi_split_group: "main_building"

  - zone_name: "Основна кухня"
    climate_entity: climate.main_kitchen_ac
    room_temp_sensor: sensor.main_kitchen_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 21.0
    multi_split_group: "main_building"

  # === ГОСТЬОВИЙ БУДИНОК ===
  - zone_name: "Гостьова спальня"
    climate_entity: climate.guest_bedroom_ac
    room_temp_sensor: sensor.guest_bedroom_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 20.0
    multi_split_group: "guest_building"

  - zone_name: "Гостьова вітальня"
    climate_entity: climate.guest_living_ac
    room_temp_sensor: sensor.guest_living_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 21.0
    multi_split_group: "guest_building"
```

**Результат:**
- Основний будинок (3 зони): працюють разом
- Гостьовий будинок (2 зони): працюють разом, але незалежно від основного

---

## Приклад 5: Складна конфігурація

**Ситуація:** Великий будинок з трьома мультиспліт системами та одним окремим блоком.

```yaml
smart_climate_controller:
  # === СИСТЕМА 1: Перший поверх (денна зона) ===
  - zone_name: "Вітальня"
    climate_entity: climate.floor1_living_ac
    room_temp_sensor: sensor.floor1_living_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 22.0
    multi_split_group: "day_zone"

  - zone_name: "Їдальня"
    climate_entity: climate.floor1_dining_ac
    room_temp_sensor: sensor.floor1_dining_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 21.5
    multi_split_group: "day_zone"

  - zone_name: "Кухня"
    climate_entity: climate.floor1_kitchen_ac
    room_temp_sensor: sensor.floor1_kitchen_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 21.0
    multi_split_group: "day_zone"

  # === СИСТЕМА 2: Другий поверх (нічна зона) ===
  - zone_name: "Головна спальня"
    climate_entity: climate.floor2_master_ac
    room_temp_sensor: sensor.floor2_master_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 20.0
    multi_split_group: "night_zone"

  - zone_name: "Спальня 2"
    climate_entity: climate.floor2_bedroom2_ac
    room_temp_sensor: sensor.floor2_bedroom2_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 21.0
    multi_split_group: "night_zone"

  - zone_name: "Спальня 3"
    climate_entity: climate.floor2_bedroom3_ac
    room_temp_sensor: sensor.floor2_bedroom3_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 21.0
    multi_split_group: "night_zone"

  - zone_name: "Ванна кімната"
    climate_entity: climate.floor2_bathroom_ac
    room_temp_sensor: sensor.floor2_bathroom_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 23.0
    multi_split_group: "night_zone"

  # === СИСТЕМА 3: Підвал ===
  - zone_name: "Спортзал"
    climate_entity: climate.basement_gym_ac
    room_temp_sensor: sensor.basement_gym_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 19.0
    multi_split_group: "basement"

  - zone_name: "Сауна зона"
    climate_entity: climate.basement_sauna_ac
    room_temp_sensor: sensor.basement_sauna_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 18.0
    multi_split_group: "basement"

  # === ОКРЕМИЙ БЛОК: Гараж ===
  - zone_name: "Гараж"
    climate_entity: climate.garage_ac
    room_temp_sensor: sensor.garage_temp
    outdoor_temp_sensor: sensor.outdoor_temperature
    target_temp: 15.0
    # Без multi_split_group
```

**Результат:**
- **Система "day_zone"**: 3 зони (вітальня, їдальня, кухня)
- **Система "night_zone"**: 4 зони (спальні + ванна)
- **Система "basement"**: 2 зони (спортзал, сауна)
- **Гараж**: 1 окремий блок, працює незалежно

Всього: 3 мультиспліт групи + 1 окремий блок = 10 зон

---

## Швидка перевірка налаштування

Після створення інтеграцій перевірте:

### 1. Developer Tools → States

Знайдіть свої climate entities і перевірте атрибут `multi_split_group`:

```yaml
climate.smart_climate_controller_bedroom:
  attributes:
    multi_split_group: "my_home"    # ← Має співпадати з іншими зонами
    group_shared_mode: "heat"       # ← Поточний режим групи
```

### 2. Лог файли

У логах Home Assistant шукайте:

```
[smart_climate_controller] Registered multi-split group: my_home
[smart_climate_controller] Added zone Спальня to multi-split group my_home
[smart_climate_controller] Added zone Вітальня to multi-split group my_home
[smart_climate_controller] Added zone Кухня to multi-split group my_home
```

### 3. Перевірка координації

Спробуйте:
1. Встановіть різні цільові температури для різних зон
2. Зачекайте кілька циклів керування
3. Перевірте, що всі зони в групі працюють в одному режимі (HEAT або COOL)

---

## Поширені помилки

### ❌ Помилка 1: Різні ID для однієї системи

```yaml
# НЕПРАВИЛЬНО - зони не об'єднаються
- zone_name: "Спальня"
  multi_split_group: "bedroom_system"

- zone_name: "Вітальня"
  multi_split_group: "living_system"    # ← Різні ID!
```

```yaml
# ПРАВИЛЬНО - всі в одній групі
- zone_name: "Спальня"
  multi_split_group: "my_home"

- zone_name: "Вітальня"
  multi_split_group: "my_home"         # ← Однаковий ID
```

### ❌ Помилка 2: Опечатки в ID

```yaml
# НЕПРАВИЛЬНО - опечатка у другій зоні
- zone_name: "Спальня"
  multi_split_group: "main_house"

- zone_name: "Вітальня"
  multi_split_group: "main_hause"     # ← Опечатка!
```

### ❌ Помилка 3: Порожнє поле для мультиспліт

```yaml
# Зона буде працювати НЕЗАЛЕЖНО
- zone_name: "Спальня"
  multi_split_group: ""               # ← Порожнє = немає групи
```

Якщо ви хочете, щоб зона була в групі - обов'язково вкажіть ID!

---

## Підказки

### 💡 Підказка 1: Зрозумілі назви груп

Використовуйте говорячі імена:
- ✅ `main_house`, `floor_1`, `guest_building`
- ❌ `group1`, `ms1`, `abc`

### 💡 Підказка 2: Один outdoor sensor

Всі зони в одній групі можуть використовувати один датчик зовнішньої температури:

```yaml
outdoor_temp_sensor: sensor.outdoor_temperature  # Для всіх зон
```

### 💡 Підказка 3: Різні цільові температури

Кожна зона може мати свою цільову температуру:

```yaml
- zone_name: "Спальня"
  target_temp: 20.0       # Прохолодніше

- zone_name: "Вітальня"
  target_temp: 22.0       # Тепліше
```

Система знайде оптимальний компроміс!

---

**Більше інформації:** [Повне керівництво по мультиспліт системам](MULTI_SPLIT_GUIDE.md)
