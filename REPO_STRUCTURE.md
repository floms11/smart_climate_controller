# Repository Structure

Цей репозиторій організований відповідно до вимог HACS для custom integrations.

## Root Level

```
smart_climate_controller/
├── custom_components/           # HACS requirement
│   └── smart_climate_controller/  # Integration folder
│       ├── __init__.py
│       ├── manifest.json
│       ├── const.py
│       ├── ... (всі файли інтеграції)
│
├── README.md                    # Main documentation
├── LICENSE                      # MIT License
├── hacs.json                    # HACS metadata
├── .gitignore
│
├── CHANGELOG.md                 # Version history
├── ARCHITECTURE.md              # Architecture details
├── INSTALLATION.md              # Step-by-step installation
├── TESTING_GUIDE.md             # Testing instructions
├── CONTRIBUTING.md              # Contribution guidelines
├── ROADMAP.md                   # Future plans
└── QUICKSTART.md                # Quick start guide
```

## Integration Structure

```
custom_components/smart_climate_controller/
├── Core Integration Files
│   ├── __init__.py              # Entry point
│   ├── manifest.json            # Integration metadata
│   ├── const.py                 # Constants
│   ├── coordinator.py           # Data coordinator
│   ├── config_flow.py           # Configuration UI
│   ├── diagnostics.py           # Diagnostics support
│
├── Entity Platforms
│   ├── climate.py               # Climate entity
│   ├── sensor.py                # Sensor entities
│
├── Configuration
│   ├── services.yaml            # Service definitions
│   ├── strings.json             # UI strings
│   └── translations/
│       └── en.json              # English translation
│
├── Domain Layer (Business Logic)
│   └── domain/
│       ├── models.py            # Domain models
│       ├── value_objects.py     # Value objects
│       ├── policies/            # Strategy policies
│       │   ├── base.py
│       │   ├── mode_selection.py
│       │   ├── setpoint_adjustment.py
│       │   └── safety.py
│       └── services/
│           └── decision_engine.py
│
├── Application Layer (Orchestration)
│   └── application/
│       ├── controller.py        # Main controller
│       ├── mapper.py            # DTO mapping
│       └── commands.py          # Command objects
│
└── Infrastructure Layer (HA Adapters)
    └── infrastructure/
        ├── ha_state.py          # State reader
        ├── ha_commands.py       # Command sender
        └── device_adapters/     # Device abstractions
            ├── base.py
            └── climate_adapter.py
```

## HACS Compliance

### Required Files

✅ `hacs.json` — HACS metadata
✅ `README.md` — Main documentation
✅ `custom_components/<domain>/manifest.json` — Integration manifest

### Directory Structure

✅ Integration files в `custom_components/smart_climate_controller/`
✅ Documentation на root level
✅ `.gitignore` для exclusions

### manifest.json Requirements

```json
{
  "domain": "smart_climate_controller",
  "name": "Smart Climate Controller",
  "version": "0.1.0",
  "documentation": "https://github.com/floms/smart_climate_controller",
  "issue_tracker": "https://github.com/floms/smart_climate_controller/issues",
  "dependencies": [],
  "codeowners": ["@floms"],
  "requirements": [],
  "config_flow": true,
  "iot_class": "calculated"
}
```

## Installation Paths

### HACS Install
HACS automatically installs to:
```
/config/custom_components/smart_climate_controller/
```

### Manual Install
Copy entire `custom_components/smart_climate_controller/` folder to:
```
/config/custom_components/smart_climate_controller/
```

## Development

### Local Development
For development, symlink the integration folder:
```bash
cd /config/custom_components
ln -s /path/to/repo/custom_components/smart_climate_controller smart_climate_controller
```

### Testing Changes
After changes:
1. Restart Home Assistant
2. Check logs for errors
3. Test functionality

## Documentation

### User-Facing Docs
- **README.md** — Overview and features
- **QUICKSTART.md** — 5-minute setup
- **INSTALLATION.md** — Detailed installation

### Developer Docs
- **ARCHITECTURE.md** — Architecture explanation
- **TESTING_GUIDE.md** — Testing approach
- **CONTRIBUTING.md** — How to contribute

### Project Management
- **ROADMAP.md** — Future plans
- **CHANGELOG.md** — Version history

## Version Control

### Branching
- `main` — stable releases
- `develop` — development branch
- `feature/*` — feature branches
- `fix/*` — bugfix branches

### Releases
Releases are tagged with semantic versioning:
- `v0.1.0` — MVP
- `v0.2.0` — Minor update
- `v1.0.0` — Major stable release

### Commit Convention
Using Conventional Commits:
```
feat(domain): add new feature
fix(coordinator): fix bug
docs: update README
refactor(policies): improve code structure
```

## File Purposes

### Integration Files
- `__init__.py` — Setup/teardown, service registration
- `coordinator.py` — Control cycle execution
- `climate.py` — Climate entity presentation
- `sensor.py` — Debug sensors
- `config_flow.py` — UI configuration

### Domain Layer
- `decision_engine.py` — Core business logic
- `policies/*` — Pluggable strategies
- `value_objects.py` — Domain primitives

### Infrastructure
- `ha_state.py` — Read HA state
- `ha_commands.py` — Send HA commands
- `device_adapters/*` — Device abstractions

## Extending

### Adding New Policy
1. Create `domain/policies/my_policy.py`
2. Implement policy interface
3. Inject in `application/controller.py`

### Adding New Device Type
1. Create `infrastructure/device_adapters/my_device_adapter.py`
2. Implement `ClimateDeviceAdapter` interface
3. Use in coordinator

### Adding New Entity
1. Create platform file (e.g., `switch.py`)
2. Add platform to `PLATFORMS` in `__init__.py`
3. Implement entity class

## Best Practices

1. ✅ Keep domain logic HA-agnostic
2. ✅ Use type hints everywhere
3. ✅ Document public APIs
4. ✅ Update CHANGELOG on changes
5. ✅ Test before committing
6. ✅ Follow existing code style

## Resources

- [HACS Documentation](https://hacs.xyz/)
- [HA Integration Dev Docs](https://developers.home-assistant.io/)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
