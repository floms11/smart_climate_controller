# Changelog

All notable changes to Smart Climate Controller will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Multi-device zone support
- Recuperator integration
- Humidity and CO₂ sensors support
- Window/door sensor integration
- PID-based setpoint adjustment

## [0.1.0] - 2026-04-16

### Added - MVP Release

#### Core Features
- **Continuous Setpoint Control**: Primary control mechanism through AC setpoint modulation
- **Outdoor-Aware Mode Selection**: Automatic heat/cool mode selection based on outdoor temperature
- **Intelligent Deadband**: Temperature stabilization zone without aggressive on/off cycling
- **Mode Switch Protection**: Hysteresis and minimum interval protection against mode oscillation
- **Temperature Rate Tracking**: Tracks temperature change velocity for predictive control
- **Safety Limits**: Emergency stop on critical temperature limits

#### Architecture
- **Clean Architecture**: 4-layer architecture (Domain, Application, Infrastructure, Presentation)
- **Domain Layer**: Pure business logic, Home Assistant agnostic
- **Strategy Pattern**: Pluggable policies for mode selection, setpoint adjustment, safety
- **Device Abstraction**: Adapter pattern ready for multiple device types

#### Policies
- `OutdoorAwareModeSelectionPolicy`: Mode selection with outdoor temperature awareness
- `DynamicSetpointAdjustmentPolicy`: Setpoint calculation with base + error + rate offsets
- `BasicSafetyPolicy`: Temperature limit safety checks

#### User Interface
- Climate entity with AUTO/OFF modes
- Debug sensors: outdoor temperature, desired setpoint, control decision
- Rich diagnostic attributes
- Config flow for easy setup
- Options flow for advanced configuration

#### Configuration
- Target temperature
- Deadband (stabilization zone)
- Min/max room temperature limits
- Base AC setpoint offset
- Dynamic rate factor and max offset
- Outdoor heat/cool thresholds
- Mode switch hysteresis
- Minimum mode switch interval
- Control cycle interval

#### Integration
- Config entry based setup
- Data update coordinator
- Services: `set_target_temperature`, `force_update`
- Diagnostics support
- Restore state on restart

#### Documentation
- Comprehensive README
- Architecture documentation
- Installation guide
- Testing guide
- Roadmap

### Technical Details
- Minimum Home Assistant version: 2024.1.0
- Python 3.11+
- Type hints throughout
- Async/await patterns
- No external dependencies

---

## Development Notes

### Version Strategy

- **0.x.y**: Development/beta versions
  - 0.1.x: MVP, single zone, single device
  - 0.2.x: Enhanced single-zone control
  - 0.3.x: Additional sensors support
  - 0.4.x: Multi-device zone
  - 0.5.x: Recuperator support
  - 0.6.x: Multi-split systems
  - 0.7.x: Multi-zone orchestration
  - 0.9.x: Release candidates for 1.0

- **1.0.0**: First stable release
  - Stable API
  - Production ready
  - Full documentation
  - Test coverage >80%

- **1.x.y**: Feature releases (backward compatible)
- **2.0.0**: Major version (breaking changes if needed)

### Commit Message Format

Following Conventional Commits:

- `feat:` New feature
- `fix:` Bug fix
- `docs:` Documentation changes
- `refactor:` Code refactoring
- `test:` Test additions/changes
- `chore:` Maintenance tasks

Example:
```
feat(domain): add PID-based setpoint adjustment policy

Implements PID controller for smoother temperature convergence.
Includes tuning parameters in config flow.

Closes #42
```

---

## Migration Guides

### Upgrading to 0.2.x (future)

When released, 0.2.x will be backward compatible with 0.1.x.
No configuration changes required.

New optional features:
- Additional sensor support (humidity, CO₂)
- Improved setpoint algorithms

---

## Breaking Changes Log

### None yet

This project aims to maintain backward compatibility within major versions.

---

**Maintainer**: @floms
**License**: MIT
