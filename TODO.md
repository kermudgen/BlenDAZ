# BlenDAZ - TODO

**Last Updated**: 2026-02-16

Track current development tasks, future features, and improvements needed.

---

## 🚧 Current Work

### PoseBridge Phase 1 MVP

**Description**: Fixed control points with basic click-drag rotation for visual posing

#### Immediate Tasks
- [ ] Complete hover detection implementation
- [ ] Verify click-drag rotation works correctly with all control points
- [ ] Test with Genesis 8 character
- [ ] Test with Genesis 9 character
- [ ] Validate rotation limits are properly enforced

#### Current Status
**Phase**: Phase 1 MVP (Fixed control points, basic rotation)
**Goal**: Complete basic visual posing with fixed 2D control points
**Next Steps**: Complete testing checklist in [posebridge/TESTING_POSEBRIDGE.md](posebridge/TESTING_POSEBRIDGE.md)

---

## ✅ Recently Completed (2026-02-16)

- [x] **Documentation System Setup** - Established four-file documentation system (CLAUDE.md, INDEX.md, SCRATCHPAD.md, TODO.md)
- [x] **INDEX.md Creation** - Comprehensive file reference with 30+ files cataloged
- [x] **CLAUDE.md Enhancement** - Added documentation system guidelines for AI assistants
- [x] **SCRATCHPAD.md Creation** - Development journal started

---

## 📋 Backlog - High Priority

### PoseBridge Development
- [ ] Complete Phase 1 MVP testing and validation
- [ ] Fix any bugs discovered during Phase 1 testing
- [ ] Archive [posebridge/scratchpad.md](posebridge/scratchpad.md) (currently 46KB, approaching 50-75KB threshold)
- [ ] Begin Phase 2 planning (directional gestures)

### Code Quality
- [ ] Refactor [daz_bone_select.py](daz_bone_select.py) - Currently 267KB (unusually large)
  - Split into logical modules
  - Identify core functionality vs. helpers
  - Maintain backwards compatibility
- [ ] Review and implement [PROPOSAL_MODULE_REFACTOR.md](PROPOSAL_MODULE_REFACTOR.md) if relevant

### Testing & Validation
- [ ] Run [test_powerpose.py](test_powerpose.py) to ensure PowerPose functionality
- [ ] Run [validate_powerpose.py](validate_powerpose.py) to check installation
- [ ] Create automated tests for PoseBridge core functionality
- [ ] Create automated tests for PoseBlend core functionality

---

## 🔮 Future Features

### PoseBridge Phases
- [ ] **Phase 2**: Directional gestures (horizontal/vertical drag for different rotation axes)
- [ ] **Phase 3**: Panel views (head detail panel, hand detail panels)
- [ ] **Phase 4**: Multi-character support (select which character to pose)
- [ ] **Phase 5**: Polish and optimization (performance improvements, visual refinements)

### PoseBlend Enhancements
- [ ] Improve pose blending algorithms
- [ ] Add more preset collections
- [ ] Enhance grid visualization
- [ ] Add pose thumbnails/previews
- [ ] Implement pose tagging and search

### Diffeomorphic Integration
- [ ] Better handling of characters without LIMIT_ROTATION constraints
- [ ] Automatic detection of Genesis version (8 vs 9)
- [ ] Support for Genesis 3 and earlier versions
- [ ] Custom rig support beyond Genesis

### UI/UX Improvements
- [ ] Implement UI polish suggestions from [UI_POLISH_DESIGN_DOCUMENT.md](UI_POLISH_DESIGN_DOCUMENT.md)
- [ ] Add keyboard shortcuts reference panel
- [ ] Create interactive tutorial/onboarding
- [ ] Add tooltips to all controls

### Performance
- [ ] Optimize GPU drawing for large control point sets
- [ ] Profile and optimize modal operator performance
- [ ] Reduce memory footprint for outline generation
- [ ] Cache frequently accessed bone data

---

## 🐛 Known Issues

### High Priority
- [ ] **Diffeomorphic Import Issue**: Some bones don't get LIMIT_ROTATION constraints
  - Affects: head, shoulder twist, elbow, forearm twist bones
  - Workaround: Fallback to IK limits or defaults in `enforce_rotation_limits()`
  - Permanent fix: Investigate Diffeomorphic import settings

### Medium Priority
- [ ] **Module Caching**: Blender module caching can cause issues during development
  - Workaround: Restart Blender or use reload scripts
  - Consider: Better reload mechanism or development mode
- [ ] **Control Point Recapture**: Must manually recapture after moving outline
  - Current: Run [recapture_control_points.py](posebridge/recapture_control_points.py)
  - Desired: Automatic recapture or validation warning

### Low Priority
- [ ] Large file size for [daz_bone_select.py](daz_bone_select.py) (267KB)
- [ ] [posebridge/scratchpad.md](posebridge/scratchpad.md) approaching archive size (46KB)

---

## 🔧 Technical Debt

### Code Quality
- [ ] Refactor [daz_bone_select.py](daz_bone_select.py) into smaller modules
- [ ] Review and clean up experimental outline generators
  - Keep: [outline_generator_lineart.py](posebridge/outline_generator_lineart.py) (primary method)
  - Archive or remove: outline_generator.py, outline_generator_body.py, outline_generator_curves.py, outline_generator_simple.py
- [ ] Standardize error handling across all modules
- [ ] Add type hints to function signatures
- [ ] Remove unused imports

### Testing
- [ ] Create unit tests for [daz_shared_utils.py](daz_shared_utils.py)
  - Test rotation limit enforcement
  - Test bend/twist axis detection
  - Test control point definitions
- [ ] Create integration tests for PoseBridge workflow
- [ ] Create integration tests for PoseBlend workflow
- [ ] Add test coverage reporting

### Performance
- [ ] Profile GPU draw handlers for performance bottlenecks
- [ ] Benchmark outline generation methods
- [ ] Optimize control point hover detection
- [ ] Cache bone axis calculations

### Documentation
- [ ] Create user installation guide
- [ ] Create video tutorials for key features
- [ ] Document known Diffeomorphic compatibility issues
- [ ] Create troubleshooting guide
- [ ] Add inline code documentation for complex functions
- [ ] Document GPU shader code

---

## 📊 Project Maintenance

### Regular Tasks
- [ ] Review and update SCRATCHPAD.md weekly
- [ ] Groom TODO.md (this file) weekly
- [ ] Archive SCRATCHPAD.md when it reaches 300-500 lines or 50-75KB
- [ ] Update CLAUDE.md "Current Focus" section when priorities shift
- [ ] Update INDEX.md when adding new files or changing file purposes
- [ ] Check for Blender API changes with new Blender releases

### Archiving Schedule
- [ ] **Immediate**: Archive [posebridge/scratchpad.md](posebridge/scratchpad.md) (46KB)
- [ ] Create `scratchpad_archive/` directory structure
- [ ] Establish monthly review process for archived documents

### Monitoring
- [ ] Watch for Diffeomorphic DAZ Importer updates
- [ ] Monitor Blender API deprecation warnings
- [ ] Track user feedback on GitHub/forums
- [ ] Monitor performance metrics in production use

---

## 💡 Ideas to Consider

### Experimental
- [ ] **AI-Assisted Posing**: Use pose detection AI to suggest control point adjustments
- [ ] **Pose Library Expansion**: Community-contributed pose library
- [ ] **Motion Capture Integration**: Import mocap data and convert to poses
- [ ] **Facial Expression System**: Extend control points to facial bones
- [ ] **Physics-Based Posing**: Add physics simulation for natural poses

### Research Needed
- [ ] **WebGL Export**: Can we export posed characters for web viewing?
- [ ] **VR Posing Interface**: Use VR controllers for intuitive posing
- [ ] **Pose Interpolation**: Smooth transitions between keyframe poses
- [ ] **Symmetry Tools**: Mirror poses left-to-right
- [ ] **Pose Presets by Genre**: Action, casual, portrait, etc.

### Community Features
- [ ] **Pose Sharing Platform**: Share and download community poses
- [ ] **Tutorial System**: In-app guided tutorials
- [ ] **Preset Marketplace**: Curated pose and preset collections
- [ ] **Plugin API**: Allow third-party extensions

---

## 📝 Notes

**How to use this file:**
1. Check "Current Work" for active development priorities
2. Move items from Backlog to Current Work as you begin them
3. Mark items complete and move to "Recently Completed"
4. Archive old completed items to SCRATCHPAD.md periodically (every few weeks)
5. Add new ideas to appropriate sections
6. Review and groom this file weekly

**Priority Levels:**
- **Current Work**: Active development, highest priority
- **Recently Completed**: Just finished (archive after a few weeks)
- **Backlog**: High priority, planned for next
- **Future Features**: Long-term vision, requires significant work
- **Ideas**: Brainstorming, needs validation/research

**Task Status Indicators:**
- [ ] Not started
- [x] Completed
- 🟡 In progress (use in descriptions)
- 🟢 Complete (use in descriptions)
- 🔴 Blocked (use in descriptions)
- ⏸️ Paused (use in descriptions)

---

## 🎯 Project Phases

### Phase 1: MVP (Current)
**Focus**: Get PoseBridge working with basic functionality
- Fixed control points
- Click-drag rotation
- Hover detection
- Dual viewport setup

### Phase 2: Gestures
**Focus**: Add directional gesture controls
- Horizontal drag = rotation on one axis
- Vertical drag = rotation on different axis
- Combine with modifier keys

### Phase 3: Detail Panels
**Focus**: Add focused panels for detailed work
- Head/face detail panel
- Hand detail panels (left/right)
- Foot detail panels

### Phase 4: Multi-Character
**Focus**: Support multiple characters in scene
- Character selection
- Per-character control points
- Outlining multiple characters

### Phase 5: Polish
**Focus**: Performance and user experience
- Optimization
- Visual refinements
- User testing feedback
- Documentation completion

---

## 🔗 Related Documentation

- [CLAUDE.md](CLAUDE.md) - Project context and development guidelines
- [INDEX.md](INDEX.md) - Complete file reference
- [SCRATCHPAD.md](SCRATCHPAD.md) - Development journal
- [PROJECT_SETUP_GUIDE.md](PROJECT_SETUP_GUIDE.md) - Documentation system guide

---

## 📅 Version History

**2026-02-16**: Initial TODO.md creation with documentation system setup
- Cataloged current work (PoseBridge Phase 1)
- Identified backlog items from existing documentation
- Noted technical debt (large file sizes, refactoring needs)
- Outlined 5-phase development roadmap
