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

## [0.2.0] - 2026-04-16

### Added - Multi-Split System Support

#### Core Features
- **Multi-Split System Support**: Full support for multi-split HVAC systems where multiple indoor units share one outdoor unit
- **Shared Mode Constraint**: All indoor units in a multi-split group must operate in the same mode (HEAT or COOL)
- **Intelligent Group Mode Selection**: Optimal mode selection algorithm that considers:
  - Needs of all rooms in the group
  - Safety priorities (preventing overcooling in winter)
  - Outdoor conditions
  - Urgency levels (temperature deviation from target)
- **Individual Unit Control**: Indoor units can be turned OFF independently while respecting group mode constraints
- **Automatic Mode Coordination**: System automatically coordinates mode changes across all units in the group

#### Domain Layer
- New `MultiSplitGroup` model in `domain/models.py` for representing multi-split groups
- New `MultiSplitModeSelector` service in `domain/services/multi_split_coordinator.py` for optimal group mode selection
- Enhanced `ClimateZone` model with `multi_split_group_id` attribute

#### Infrastructure
- New `MultiSplitGroupCoordinator` in `multi_split_coordinator.py` for managing multi-split groups in Home Assistant
- Integration with main coordinator for mode synchronization across zones
- Automatic group registration on zone initialization

#### Configuration
- New configuration parameter: `multi_split_group` - identifier to group zones into multi-split systems
- Automatic grouping of zones with the same `multi_split_group` ID
- Per-zone configuration with group-level coordination

#### Diagnostics
- New attributes for multi-split diagnostics:
  - `multi_split_group`: Group identifier
  - `group_shared_mode`: Current shared mode of the group
  - `last_mode_change`: Timestamp of last group mode change
- Enhanced diagnostics data with multi-split group information

#### Algorithm Features
- **Voting Logic**: Collects mode preferences from all zones
- **Urgency Weighting**: Prioritizes zones with greater temperature deviation
- **Safety Rules**:
  - Heating priority in cold outdoor conditions
  - Cooling priority in hot outdoor conditions
- **Conflict Resolution**: Intelligent tie-breaking based on urgency and outdoor conditions
- **Mode Preservation**: Maintains current mode when all zones are satisfied

### Changed
- Updated `ClimateController.execute_control_cycle()` to accept `multi_split_group_shared_mode` parameter
- Enhanced coordinator initialization to register multi-split groups
- Updated version to 0.2.0 in manifest.json

### Technical Details
- Backward compatible with 0.1.x single-zone configurations
- No configuration migration required
- Multi-split features are optional - activate by setting `multi_split_group` parameter

## [0.1.1] - 2026-04-16

### Fixed
- Fixed `outdoor_forbids_cooling` variable initialization in mode selection policy
- Ensured both `outdoor_forbids_heating` and `outdoor_forbids_cooling` are initialized in all code paths

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
  - 0.2.x: Multi-split systems ✅
  - 0.3.x: Enhanced single-zone control & additional sensors support
  - 0.4.x: Multi-device zone
  - 0.5.x: Recuperator support
  - 0.6.x: Advanced multi-zone orchestration
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
