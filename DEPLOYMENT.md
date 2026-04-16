# Deployment Guide — Публікація інтеграції

Інструкція як опублікувати Smart Climate Controller на GitHub та додати до HACS.

## Крок 1: Підготовка репозиторію

### 1.1 Ініціалізація Git

```bash
cd /path/to/smart_climate_controller_repo

# Initialize git
git init

# Add all files
git add .

# Initial commit
git commit -m "feat: initial release v0.1.0

- Clean architecture with 4 layers
- Continuous setpoint control
- Outdoor-aware mode selection
- Intelligent deadband
- Mode switch protection
- Temperature rate tracking
- Safety limits
- Config flow + options flow
- Debug sensors
- Full documentation"
```

### 1.2 Створення GitHub Repository

1. Перейдіть на https://github.com/new
2. Repository name: `smart_climate_controller`
3. Description: `Smart Climate Controller for Home Assistant — Advanced climate control with outdoor awareness and continuous setpoint modulation`
4. Public repository
5. **НЕ додавайте** README, .gitignore, license (вони вже є)
6. Create repository

### 1.3 Push до GitHub

```bash
# Add remote
git remote add origin https://github.com/floms/smart_climate_controller.git

# Rename branch to main (if needed)
git branch -M main

# Push
git push -u origin main
```

## Крок 2: Release

### 2.1 Створення тега

```bash
# Create annotated tag
git tag -a v0.1.0 -m "Release v0.1.0 - MVP

Features:
- Continuous setpoint control
- Outdoor-aware mode selection
- Intelligent deadband behavior
- Mode switch protection
- Temperature rate tracking
- Safety limits

See CHANGELOG.md for full details."

# Push tag
git push origin v0.1.0
```

### 2.2 GitHub Release

1. На GitHub: Releases → Create a new release
2. Choose tag: `v0.1.0`
3. Release title: `v0.1.0 — MVP Release`
4. Description:

```markdown
# Smart Climate Controller v0.1.0 — MVP Release 🎉

First stable release of Smart Climate Controller!

## 🌟 Features

- **Continuous Setpoint Control** — Primary mechanism through AC setpoint modulation
- **Outdoor-Aware Mode Selection** — Intelligent heat/cool selection based on outdoor temperature
- **Intelligent Deadband** — Device stays running within stabilization zone
- **Mode Switch Protection** — Hysteresis and minimum intervals prevent oscillation
- **Temperature Rate Tracking** — Predictive control based on temperature change velocity
- **Safety Limits** — Emergency stop on critical temperatures

## 📦 Installation

### Via HACS (Recommended)
1. HACS → Integrations → ⋮ → Custom repositories
2. Add: `https://github.com/floms/smart_climate_controller`
3. Category: Integration
4. Install "Smart Climate Controller"
5. Restart Home Assistant

### Manual Installation
1. Download `smart_climate_controller.zip` below
2. Extract to `/config/custom_components/`
3. Restart Home Assistant

## 📖 Documentation

- [Quick Start Guide](QUICKSTART.md)
- [Installation Guide](INSTALLATION.md)
- [Architecture Details](ARCHITECTURE.md)
- [Testing Guide](TESTING_GUIDE.md)

## 🐛 Known Issues

None yet! Report issues at https://github.com/floms/smart_climate_controller/issues

## 🚀 Next Steps

See [ROADMAP.md](ROADMAP.md) for planned features.

---

**Full Changelog**: https://github.com/floms/smart_climate_controller/commits/v0.1.0
```

5. Attachments: GitHub automatically creates source archives
6. Publish release ✅

## Крок 3: HACS Integration

### 3.1 Перевірка HACS Compliance

Перевірте чи є:
- ✅ `hacs.json` у корені
- ✅ `custom_components/<domain>/` структура
- ✅ `manifest.json` з правильними полями
- ✅ README.md
- ✅ Релізи з тегами

### 3.2 Тестування через Custom Repository

Перш ніж подавати до default HACS:

1. У своєму HA: HACS → Integrations → ⋮
2. Custom repositories
3. Додати: `https://github.com/floms/smart_climate_controller`
4. Category: Integration
5. Встановити та протестувати

### 3.3 Подання до HACS Default

**Зачекайте кілька тижнів** після релізу для збору відгуків.

Потім:
1. Fork https://github.com/hacs/default
2. Додати integration до `repositories.json`:
```json
{
  "smart_climate_controller": {
    "name": "Smart Climate Controller",
    "domains": ["climate", "sensor"],
    "iot_class": "calculated"
  }
}
```
3. Create PR з описом інтеграції
4. Дочекатись review та merge

## Крок 4: Post-Release

### 4.1 Оновлення документації

Після публікації оновити:

**README.md**:
- ✅ Видалити "(коли додасте в HACS)"
- ✅ Додати badges (версія, HACS, downloads)
- ✅ Додати screenshots/demo

**INSTALLATION.md**:
- ✅ Конкретні інструкції з URL

### 4.2 Community Outreach

Анонсувати на:
- Home Assistant Community Forum
- Reddit r/homeassistant
- Home Assistant Discord
- Twitter/X #HomeAssistant

Приклад поста:
```
🎉 Представляю Smart Climate Controller — кастомна інтеграція HA
для розумного керування кліматом!

✨ Особливості:
- Безперервна модуляція уставки (не on/off!)
- Врахування зовнішньої температури
- Clean Architecture
- Готово до розширення (multi-device, multi-zone)

🔗 GitHub: https://github.com/floms/smart_climate_controller
📖 Docs: детальна документація та гайди

#HomeAssistant #SmartHome #HVAC
```

### 4.3 Issue Templates

Створити `.github/ISSUE_TEMPLATE/`:

**bug_report.md**:
```yaml
---
name: Bug Report
about: Report a bug
title: '[BUG] '
labels: bug
---

**Describe the bug**
A clear description of the bug.

**Version**
Integration version:

**Configuration**
- Target temp:
- Outdoor thresholds:
- Min mode switch interval:

**Logs**
```
Paste logs here
```

**Diagnostics**
Attach downloaded diagnostics file.
```

**feature_request.md**:
```yaml
---
name: Feature Request
about: Suggest a feature
title: '[FEATURE] '
labels: enhancement
---

**Feature Description**
Clear description of the feature.

**Use Case**
Why is this needed?

**Proposed Solution**
How should it work?
```

### 4.4 GitHub Actions (Optional)

Створити `.github/workflows/`:

**validate.yml** — валідація на кожен push:
```yaml
name: Validate

on: [push, pull_request]

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install HACS validator
        run: pip install homeassistant
      - name: Validate manifest
        run: python -m homeassistant.components.manifest validate custom_components/smart_climate_controller/manifest.json
```

## Крок 5: Maintenance

### Регулярні задачі:

**Щотижня**:
- Відповідати на issues
- Review pull requests
- Оновлювати docs якщо потрібно

**Щомісяця**:
- Планувати наступні features
- Оновлювати ROADMAP
- Аналізувати використання

**На кожен release**:
- Оновити CHANGELOG
- Створити tag
- GitHub release
- Announcement

### Versioning Strategy

- **Patch** (0.1.x): Bugfixes, minor improvements
- **Minor** (0.x.0): New features, backward compatible
- **Major** (x.0.0): Breaking changes

Приклад:
```
v0.1.0 → MVP release
v0.1.1 → Bugfix: fix coordinator error
v0.2.0 → Feature: add humidity sensor support
v1.0.0 → Stable API, production ready
```

## Checklist перед релізом

- [ ] Всі файли committed та pushed
- [ ] Version в manifest.json оновлена
- [ ] CHANGELOG.md оновлений
- [ ] README актуальний
- [ ] Git tag створений
- [ ] GitHub release опублікований
- [ ] Протестовано установку через HACS custom repo
- [ ] Документація перевірена
- [ ] Issue templates створені
- [ ] Announcement готовий

## Support

Підтримка користувачів:
- GitHub Issues для bug reports
- GitHub Discussions для питань
- Home Assistant Community Forum thread

## Analytics (Optional)

Можна трекати:
- GitHub stars/forks
- HACS downloads (коли в default)
- Issue velocity
- Community engagement

Використовувати для планування розвитку.

---

**Готово до публікації!** 🚀

Весь код готовий, документація повна, структура HACS-compliant.
