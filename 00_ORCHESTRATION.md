# OVERNIGHT IMPLEMENTATION - ORCHESTRATION
**Duration:** 6-8 hours | **Autonomous Execution** | **Multi-file Plan**

---

## 🎯 MISSION

Implementeer Agent Lifecycle, Training Workflow, en HR Manager features uit Product Spec v1.1 zonder menselijke tussenkomst. Elke taak is een apart document dat sequentieel wordt uitgevoerd.

---

## 📋 EXECUTION ORDER

Work through these documents **IN ORDER**. Do NOT skip ahead.

```
START HERE
    ↓
[00_ORCHESTRATION.md] ← You are here
    ↓
[01_AGENT_LIFECYCLE.md] (2 hours)
    ↓
[02_TRAINING_WORKFLOW.md] (2 hours)
    ↓
[03_HR_MANAGER.md] (2 hours)
    ↓
[04_FRONTEND_UI.md] (1.5 hours)
    ↓
[05_TESTING_DEPLOYMENT.md] (0.5 hours)
    ↓
DONE - Wake human for verification
```

---

## 🔧 CORE PRINCIPLES (Apply to ALL tasks)

### DRY (Don't Repeat Yourself)
```python
# ❌ BAD - Duplicated logic
# File 1:
pool = await init_db_pool()
loader = SkillLoader(pool)
skills = await loader.get_agent_skills(agent_id)

# File 2:
pool = await init_db_pool()
loader = SkillLoader(pool)
skills = await loader.get_agent_skills(agent_id)

# ✅ GOOD - Shared helper
# agents/shared/skill_helpers.py
async def load_agent_skills(agent_id: str, task_context: dict):
    """Shared skill loading logic"""
    pool = await init_db_pool()
    if not pool or not agent_id:
        return [], []
    loader = SkillLoader(pool)
    skills = await loader.get_agent_skills(agent_id)
    applicable = loader.determine_applicable_skills(skills, task_context)
    context = loader.compose_skill_context(applicable)
    return context, [s['skill_id'] for s in applicable]

# File 1 & 2:
from agents.shared.skill_helpers import load_agent_skills
context, skill_ids = await load_agent_skills(agent_id, task_context)
```

### Reusability
- Extract repeated patterns into functions
- Create shared modules for cross-cutting concerns
- Use constants for magic values

### Maintainability
- Change logic in ONE place only
- Clear function names
- Document complex logic

### Naming
- `create_agent()` not `ca()`
- `validate_training_url()` not `vtu()`
- Be explicit, be clear

**When refactoring:** Document what duplication you found and how you fixed it in your commit message.

---

## 🚦 STOP CONDITIONS

**STOP and report to human if:**

1. **Test Failure:** Any test suite fails after implementation
2. **Syntax Error:** Python syntax errors that prevent import
3. **Database Error:** Migration failures or constraint violations
4. **Circular Import:** Import cycle detected
5. **Missing Dependency:** Required module/package not found

**DO NOT:**
- Continue if tests are red
- Skip error handling
- Deploy broken code
- Proceed without verification

**INSTEAD:**
- Document the error clearly
- Show stack trace
- Suggest fix
- Wait for human

---

## ✅ DONE CRITERIA (per document)

Each task document has specific acceptance criteria. A task is DONE when:

1. ✅ Code implemented
2. ✅ Tests written (if applicable)
3. ✅ No syntax errors
4. ✅ Committed with clear message
5. ✅ Verified via query/log check (if applicable)

---

## 📊 PROGRESS TRACKING

Update this section after EACH task:

```
[00_ORCHESTRATION.md]    ✅ Read
[01_AGENT_LIFECYCLE.md]  ⬜ Not Started
[02_TRAINING_WORKFLOW.md] ⬜ Not Started
[03_HR_MANAGER.md]        ✅ Complete
[04_FRONTEND_UI.md]       ⬜ Not Started
[05_TESTING_DEPLOYMENT.md] ⬜ Not Started
```

**Update after each document completion!**

---

## 🔄 WORKFLOW PER TASK

For EACH document (01-05):

1. **Read Entire Document**
   - Understand requirements
   - Note dependencies
   - Check prerequisites

2. **Implement Code**
   - Follow DRY principles
   - Add error handling
   - Use type hints

3. **Write Tests** (if specified)
   - Unit tests for functions
   - Integration tests for flows

4. **Commit**
   - Clear commit message
   - Reference document number
   - Describe changes

5. **Verify**
   - Run specified checks
   - Confirm acceptance criteria
   - Document any issues

6. **Mark Complete**
   - Update progress tracker above
   - Move to next document

---

## 🛠️ ENVIRONMENT SETUP

**Repository:** `/home/exedev/wonderz-agentics`  
**Branch:** `fix/artifact-storage-and-settings` (continue using this)  
**Python:** 3.12  
**Database:** Postgres with pgvector

**Available tools:**
- Git (commit, push)
- Python (implementation)
- psql (database queries)
- pytest (testing)

**NOT available:**
- Service restart (requires sudo)
- DNS resolution for git push (may fail)
- Package installation (pip may fail)

**Workarounds:**
- If git push fails: Document in commit log, human will push
- If sudo needed: Document action needed, continue
- If pip fails: Use existing packages only

---

## 📁 FILE STRUCTURE

**Backend:**
```
app/
  routes/
    agents.py        ← Agent CRUD endpoints
    training.py      ← Training endpoints
    hr.py            ← HR endpoints
  services/
    skill_loader.py  ← Already implemented ✅
    training.py      ← NEW - Training workflow
  orchestration/
    manager.py       ← Existing, may need updates
agents/
  shared/
    skill_helpers.py ← NEW - Shared helpers (DRY)
workers/
  tasks.py          ← Existing, may need updates
```

**Frontend:**
```
frontend/src/
  components/
    AgentCard.jsx           ← NEW - Agent display
    AgentForm.jsx           ← NEW - Create/edit agent
    TrainingPanel.jsx       ← NEW - Training interface
    DevelopmentPoints.jsx   ← NEW - HR dashboard
  pages/
    AgentsOverview.jsx      ← NEW - All agents
    AgentDetails.jsx        ← NEW - Single agent
    TrainingHub.jsx         ← NEW - Training center
    HRDashboard.jsx         ← NEW - HR manager
```

---

## 🔗 DEPENDENCIES BETWEEN TASKS

```
01_AGENT_LIFECYCLE
  ↓ (agents must exist before training)
02_TRAINING_WORKFLOW
  ↓ (training creates development points)
03_HR_MANAGER
  ↓ (HR dashboard shows agents & training)
04_FRONTEND_UI
  ↓ (UI tests everything)
05_TESTING_DEPLOYMENT
```

**DO NOT skip tasks or change order!**

---

## 📝 COMMIT MESSAGE FORMAT

```
[TaskXX] Feature: Brief description

WHAT:
- Bullet points of changes

WHY:
- Reason for changes

TESTING:
- How to verify

DRY:
- Any refactoring done to eliminate duplication

Refs: Product Spec v1.1 Section X
```

**Example:**
```
[Task01] Feature: Agent CRUD endpoints

WHAT:
- Added POST /api/agents for agent creation
- Added GET /api/agents for listing
- Added PATCH /api/agents/{id} for updates
- Extracted agent validation into shared validator

WHY:
- Users need to create and manage agents via UI
- Enables dynamic agent hiring

TESTING:
- curl POST /api/agents with sample payload
- Check hired_agents table for new entry

DRY:
- Created shared validate_agent_config() function
- Reused across POST and PATCH endpoints

Refs: Product Spec v1.1 Section 2, Phase 1-4
```

---

## 🚀 START COMMAND

**When ready to begin overnight run:**

```bash
cd /home/exedev/wonderz-agentics
git status  # Verify clean state
git log -1  # Note current commit

# Read first task
cat 01_AGENT_LIFECYCLE.md
# Follow instructions
# Implement, test, commit
# Move to next document
```

---

## ⏰ TIME ESTIMATES

| Document | Feature | Estimate | Complexity |
|----------|---------|----------|------------|
| 01 | Agent Lifecycle | 2h | Medium |
| 02 | Training Workflow | 2h | Medium |
| 03 | HR Manager | 2h | Medium |
| 04 | Frontend UI | 1.5h | Low-Medium |
| 05 | Testing & Deploy | 0.5h | Low |
| **TOTAL** | | **8h** | |

**Buffer:** Add 20% for debugging (total ~10h)

---

## 🎯 SUCCESS METRICS

**Implementation is successful if:**

1. ✅ All 5 task documents completed
2. ✅ No syntax errors in codebase
3. ✅ All acceptance criteria met
4. ✅ Database schema updates applied
5. ✅ Code follows DRY principles
6. ✅ Commits are clear and documented

**Partial success (acceptable):**
- Git push failed (documented, human will push)
- Service restart needed (documented, human will do)
- Some tests skipped (documented reason)

**Failure (wake human):**
- Circular imports
- Database corruption
- Multiple test suites failing
- Unable to proceed with any task

---

## 📞 HUMAN HANDOFF

**When ALL tasks complete (or failure):**

Create file: `/mnt/user-data/outputs/overnight_report.md`

Include:
1. Completion status per task (✅/❌)
2. Commits made (list with hashes)
3. Tests run and results
4. Any errors encountered
5. Actions needed by human (push, restart, etc.)
6. Time taken per task
7. Overall assessment

**Then:** Present the report file and STOP.

---

## 🔐 SAFETY CHECKS

**Before EACH commit:**
- [ ] No syntax errors (`python -m py_compile <file>`)
- [ ] No obvious logic errors
- [ ] Error handling present
- [ ] Type hints used
- [ ] Docstrings added

**Before MOVING to next task:**
- [ ] Current task fully done
- [ ] Acceptance criteria verified
- [ ] Progress tracker updated
- [ ] No blocking errors

---

## 📚 REFERENCE DOCUMENTS

**Available for consultation:**
- `/mnt/project/crew_intelligent_spec_v1_3.docx` - Platform architecture
- `/mnt/project/crew_intelligent_product_spec_v1_1__1_.docx` - Product features
- `/mnt/project/crew_intelligent_status_v2.md` - Current status
- `/mnt/user-data/outputs/fase2_completion_report.md` - Skills system reference

**Read these if you need context about:**
- Database schema
- Existing architecture
- API patterns
- Skills system (already implemented)

---

## ✅ READY TO START

**Checklist before proceeding to Task 01:**
- [x] Read this orchestration document fully
- [ ] Understand DRY principles
- [ ] Know stop conditions
- [ ] Know commit format
- [ ] Ready to implement autonomously

**Next step:** Open `01_AGENT_LIFECYCLE.md` and begin implementation.

---

**Status:** READY FOR OVERNIGHT EXECUTION  
**Estimated Completion:** 8-10 hours  
**Human Review Needed After:** All tasks done OR stop condition hit

🚀 **BEGIN WITH TASK 01**
