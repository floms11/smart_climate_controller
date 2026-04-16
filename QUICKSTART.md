# Quick Start Guide

Швидкий старт для нетерплячих 🚀

## 5-хвилинне встановлення

### 1. Копіювання файлів

```bash
cd /config
mkdir -p custom_components
cp -r /path/to/smart_climate_controller custom_components/
```

### 2. Перезавантаження HA

Settings → System → Restart

### 3. Додавання інтеграції

1. Settings → Devices & Services → + ADD INTEGRATION
2. Знайти "Smart Climate Controller"
3. Заповнити:
   - Zone Name: `Спальня`
   - Climate Entity: `climate.bedroom_ac`
   - Room Sensor: `sensor.bedroom_temperature`
   - Outdoor Sensor: `sensor.outdoor_temperature`
   - Target: `21°C`
4. SUBMIT

### 4. Готово! 🎉

Інтеграція створена. Зачекайте 1-2 хвилини і перевірте:

```
climate.smart_climate_controller_bedroom
```

---

## Базова перевірка

### Подивитись стан

Developer Tools → States → знайти вашу climate entity

**Важливі атрибути**:
- `control_active: true` — контролер працює
- `outdoor_temp` — зовнішня температура
- `last_decision` — останнє рішення
- `desired_setpoint` — бажана уставка AC

### Змінити температуру

Відкрити climate entity → змінити target → зачекати 1 хв

**Очікується**: `desired_setpoint` зміниться, команда відправиться до AC

---

## Типові сценарії

### Сценарій 1: Основна робота

**Ситуація**: room = 22°C, target = 21°C, outdoor = 20°C

**Що станеться**:
1. Mode selection: cooling (бо кімната тепліша за target і outdoor теплий)
2. Setpoint calculation: ~19°C (target - base_offset)
3. Команда: `climate.set_temperature` з mode=cool, temp=19°C

**Результат**: AC почне охолоджувати до 19°C, кімната поступово охолодиться до 21°C

### Сценарій 2: Deadband

**Ситуація**: room = 21.2°C, target = 21°C (в межах deadband 0.5°C)

**Що станеться**:
1. Система розпізнає, що в deadband
2. Поточний режим зберігається
3. Setpoint плавно коригується
4. **AC НЕ ВИМИКАЄТЬСЯ**

### Сценарій 3: Зміна погоди

**Ситуація**: outdoor змінюється з 10°C на 25°C

**Що станеться**:
1. Якщо режим був heating → не переключиться одразу
2. Зачекає `min_mode_switch_interval` (30 хв за замовчуванням)
3. Після затримки переключиться на cooling
4. Повідомить причину в `last_decision_reason`

---

## Налаштування під себе

### Відкрити Options

Settings → Devices & Services → Smart Climate Controller → CONFIGURE

### Що варто змінити:

**Для більш агресивного охолодження/нагріву**:
- Base Offset: збільшити з 2.0 до 3.0-4.0

**Для швидшого перемикання режимів**:
- Min Mode Switch Interval: зменшити з 1800 до 900 (15 хв)

**Для вашого клімату**:
- Outdoor Heat Threshold: температура, нижче якої пріоритет heating
- Outdoor Cool Threshold: температура, вище якої пріоритет cooling

---

## Dashboard

### Мінімальна картка

```yaml
type: thermostat
entity: climate.smart_climate_controller_bedroom
```

### Розширена картка

```yaml
type: vertical-stack
cards:
  - type: thermostat
    entity: climate.smart_climate_controller_bedroom

  - type: entities
    entities:
      - sensor.bedroom_outdoor_temperature
      - sensor.bedroom_desired_ac_setpoint
      - sensor.bedroom_control_decision
```

---

## Автоматизації

### Нічний режим

```yaml
automation:
  - alias: "Ніч: знизити температуру"
    trigger:
      platform: time
      at: "22:00:00"
    action:
      service: climate.set_temperature
      target:
        entity_id: climate.smart_climate_controller_bedroom
      data:
        temperature: 20
```

### Away mode

```yaml
automation:
  - alias: "Відключити клімат при відсутності"
    trigger:
      platform: state
      entity_id: binary_sensor.home_occupied
      to: 'off'
      for:
        hours: 1
    action:
      service: climate.turn_off
      target:
        entity_id: climate.smart_climate_controller_bedroom
```

---

## Troubleshooting

### Не працює?

1. **Перевірте логи**: Settings → System → Logs
2. **Перевірте entities**: чи доступні sensor та climate entity?
3. **Перевірте config**: чи правильні entity_id?

### AC не реагує?

1. Подивіться `last_decision` та `last_decision_reason`
2. Можливо команда throttled (занадто рано після попередньої)
3. Можливо режим locked (занадто рано для зміни режиму)

### Хочу детальніше зрозуміти логіку?

Читайте:
- **README.md** — загальний опис
- **ARCHITECTURE.md** — архітектура
- **TESTING_GUIDE.md** — як це працює детально

---

## Наступні кроки

1. ✅ Встановлено та працює
2. 📊 Додати графіки на dashboard
3. 🤖 Налаштувати автоматизації
4. ⚙️ Тонке налаштування параметрів
5. 📖 Вивчити документацію для розуміння можливостей

---

**Потрібна допомога?** → [Issues на GitHub](https://github.com/floms/smart_climate_controller/issues)

**Все працює?** → Поділіться досвідом у [Discussions](https://github.com/floms/smart_climate_controller/discussions)
