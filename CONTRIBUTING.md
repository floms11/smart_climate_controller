# Contributing to Smart Climate Controller

Дякуємо за інтерес до проєкту! 🎉

## Як контрибутити

### Reporting Issues

Якщо знайшли баг або маєте ідею:
1. Перевірте, чи немає вже такого issue
2. Створіть новий issue з детальним описом
3. Додайте логи/діагностику якщо це баг

### Pull Requests

1. Fork репозиторій
2. Створіть feature branch (`git checkout -b feature/amazing-feature`)
3. Commit зміни (`git commit -m 'feat: add amazing feature'`)
4. Push до branch (`git push origin feature/amazing-feature`)
5. Відкрийте Pull Request

### Commit Message Format

Використовуємо [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` — нова функція
- `fix:` — виправлення бага
- `docs:` — зміни документації
- `refactor:` — рефакторинг коду
- `test:` — додавання тестів
- `chore:` — технічні зміни

Приклад:
```
feat(domain): add PID-based setpoint adjustment

Implements PID controller for better temperature control.
Includes configuration options.

Closes #42
```

### Code Style

- Python 3.11+
- Type hints обов'язкові
- Async/await де можливо
- Дотримуватись Clean Architecture принципів
- Documetation strings для публічних методів

### Testing

Перед PR переконайтесь:
- [ ] Код запускається без помилок
- [ ] Тести проходять (якщо є)
- [ ] Додали документацію для нових features
- [ ] Оновили CHANGELOG.md

### Areas for Contribution

Пріоритетні напрямки:

1. **Testing** — unit tests для domain layer
2. **Documentation** — покращення guides, examples
3. **Policies** — нові стратегії керування
4. **Device Adapters** — підтримка нових типів пристроїв
5. **UI** — custom Lovelace cards
6. **Translations** — переклади інтерфейсу

### Development Setup

```bash
# Clone repo
git clone https://github.com/floms/smart_climate_controller.git
cd smart_climate_controller

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dev dependencies (if any)
pip install -r requirements_dev.txt  # коли додамо

# Run tests
pytest tests/  # коли додамо
```

### Architecture Guidelines

При додаванні нових features:

- **Domain logic** → `domain/` (HA-agnostic)
- **HA integration** → `infrastructure/`
- **Orchestration** → `application/`
- **UI** → root level files (climate.py, sensor.py)

Не змішуйте бізнес-логіку з HA-специфікою!

### Questions?

Якщо не впевнені як контрибутити:
1. Створіть issue з питанням
2. Приєднайтесь до [Discussions](https://github.com/floms/smart_climate_controller/discussions)
3. Напишіть @floms

## Code of Conduct

Будьте дружелюбні та respectful. Ми всі тут щоб створити щось крутє разом! 🚀

## License

Контрибутячи, ви погоджуєтесь що ваш код буде під MIT License.
