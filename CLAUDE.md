# Claude Dev Workflow

This file contains custom slash commands for an AI-powered development workflow with three specialized agents.

## Workflow Commands

### /init
Initialize the Claude Dev Workflow structure in this repository.

Create the following directory structure:
```
./workflow/
├── context/
│   ├── prd.md
│   ├── tech-stack.md
│   ├── coding-standards.md
│   └── project-charter.md
├── scratchpad/
├── logs/
└── epics/
```

Copy template content to context files from the templates section below. Create a .gitignore entry to ignore logs/ and scratchpad/ but keep context/ files versioned.

Display: "✅ Claude Dev Workflow initialized! Edit ./workflow/context/ files to configure your project."

---

### /plan [issue_number]
**Role: Product Owner Agent**

Analyze GitHub issue and create a detailed implementation plan using project context.

**Context Loading:**
Load and incorporate these project documents:
- ./workflow/context/prd.md (Product Requirements)
- ./workflow/context/tech-stack.md (Technology Stack) 
- ./workflow/context/project-charter.md (Project Goals)
- ./workflow/context/coding-standards.md (Development Standards)

**Task:**
1. Analyze GitHub issue #{issue_number}
2. Create implementation plan that includes:
   - Business requirements analysis aligned with PRD
   - Acceptance criteria based on project standards
   - Technical considerations using project tech stack
   - Risk assessment and mitigation strategies
   - Success metrics and validation approach
3. Save plan to ./workflow/scratchpad/issue-{issue_number}/plan.md
4. Log activity to ./workflow/logs/planning.jsonl
5. Update GitHub issue with the plan:
   - Add comment with implementation plan summary
   - Add relevant labels (e.g., "planned", "ready-for-dev")
   - Update issue description if needed
   - Use: `gh issue comment {issue_number} --body-file ./workflow/scratchpad/issue-{issue_number}/plan.md`

**Format the plan clearly for the engineering team with sections for requirements, acceptance criteria, technical approach, and risks.**

Display: "📋 Plan created and posted to issue #{issue_number}. Next: /dev {issue_number}"

---

### /dev [issue_number]
**Role: Software Engineer Agent**

Implement the solution following GitHub Flow and project standards.

**Context Loading:**
Load project context and previous work:
- All files from ./workflow/context/ 
- ./workflow/scratchpad/issue-{issue_number}/plan.md (Implementation Plan)

**Task:**
1. Review the implementation plan thoroughly
2. Create development guidance that includes:
   - Feature branch creation: feature/issue-{issue_number}-[description]
   - Code implementation following project architecture patterns
   - Test strategy aligned with project testing standards
   - Documentation updates required
   - Pull request preparation checklist
3. Provide step-by-step implementation guidance
4. Save development notes to ./workflow/scratchpad/issue-{issue_number}/development.md
5. Log activity to ./workflow/logs/development.jsonl
6. Implement the solution and create pull request:
   - Create feature branch: `git checkout -b feature/issue-{issue_number}-[description]`
   - Implement code changes following the guidance
   - Commit changes with descriptive messages
   - Push branch: `git push -u origin feature/issue-{issue_number}-[description]`
   - Create PR: `gh pr create --title "Fix #{issue_number}: [Description]" --body-file ./workflow/scratchpad/issue-{issue_number}/development.md --base main`
   - Link to issue: `gh pr edit --add-label "issue-{issue_number}"`

**Ensure implementation follows:**
- Project tech stack requirements
- Coding standards and conventions
- Architecture patterns established in project
- Testing and quality requirements

Display: "🔧 Development complete and PR created for issue #{issue_number}. Next: /review [pr_number] {issue_number}"

---

### /review [pr_number] [issue_number]
**Role: Senior Engineering Manager Agent**

Perform comprehensive code review against project standards and requirements.

**Context Loading:**
Load complete project context and workflow history:
- All files from ./workflow/context/
- ./workflow/scratchpad/issue-{issue_number}/plan.md (if issue_number provided)
- ./workflow/scratchpad/issue-{issue_number}/development.md (if issue_number provided)

**Task:**
1. Review GitHub PR #{pr_number} comprehensively
2. Check CI/CD status and test results:
   - Run: `gh pr checks {pr_number}`
   - Review failed checks and test results
   - Analyze build logs for warnings or issues
   - Check code coverage reports
3. Evaluate against project criteria:
   - Code quality meets coding standards
   - Architecture aligns with tech stack decisions
   - Security follows project guidelines
   - Performance meets project requirements
   - Tests are adequate per project standards
   - Documentation is complete and accurate
   - Alignment with original business requirements
   - CI/CD pipeline passes all checks
4. Provide specific, actionable feedback with priority levels:
   - **Must Fix** (blocking issues that prevent merge)
   - **Should Fix** (important improvements for code quality)
   - **Consider** (optional enhancements for future iterations)
5. Save review to ./workflow/scratchpad/issue-{issue_number}/review.md
6. Log activity to ./workflow/logs/review.jsonl
7. Post review to GitHub PR:
   - Add review comments: `gh pr review {pr_number} --comment --body-file ./workflow/scratchpad/issue-{issue_number}/review.md`
   - Add merge recommendation at the end of review:
     - ✅ **READY TO MERGE** - All checks pass, code quality excellent
     - 🔄 **NEEDS CHANGES** - Must fix issues before merge
     - ⚠️ **MERGE WITH CAUTION** - Minor issues but can proceed
   - Do NOT merge - only provide recommendation

Display: "📝 Review complete for PR #{pr_number} with merge recommendation. Check GitHub PR for detailed feedback."

---

### /status
Show current workflow status and active issues.

**Task:**
1. Display current repository name
2. Check if workflow is initialized (./workflow/ exists)
3. List active issues in ./workflow/scratchpad/ with status:
   - [P] = plan.md exists
   - [D] = development.md exists  
   - [R] = review.md exists
4. Show recent activity from logs

**Example Output:**
```
Workflow Status for: my-awesome-app
✅ Initialized

Active Issues:
  Issue #123: [P][D] 
  Issue #124: [P]
  Issue #125: [P][D][R]
```

---

### /view [issue_number]
Display all workflow files for a specific issue.

**Task:**
1. Check if ./workflow/scratchpad/issue-{issue_number}/ exists
2. Display contents of all .md files in that directory:
   - plan.md (if exists)
   - development.md (if exists)
   - review.md (if exists)
3. Format output with clear section headers

Display issue contents with clear separation between plan, development, and review sections.

---

### /epic [epic_name]
Create and manage epic-level planning.

**Task:**
1. Create ./workflow/epics/{epic_name}.md
2. Include epic template with:
   - Epic description and goals
   - Success criteria
   - Timeline and milestones
   - Related issues list
   - Stakeholder requirements
3. Link to project context and constraints

---

## Template Content

### PRD Template (workflow/context/prd.md)
```markdown
# Product Requirements Document

## Project Overview
[Brief description of the project and its purpose]

## Target Users
[Who will use this product]

## Key Features
[List of main features and capabilities]

## Success Metrics
[How success will be measured]

## Constraints
[Technical, business, or resource constraints]

## Requirements
[Detailed functional and non-functional requirements]
```

### Tech Stack Template (workflow/context/tech-stack.md)
```markdown
# Technology Stack

## Frontend
[Frontend technologies, frameworks, libraries]

## Backend
[Backend technologies, frameworks, APIs]

## Database
[Database technology and structure decisions]

## Infrastructure
[Hosting, deployment, monitoring tools]

## Development Tools
[Build tools, testing frameworks, CI/CD]

## Architecture Patterns
[Design patterns and architectural decisions]
```

### Coding Standards Template (workflow/context/coding-standards.md)
```markdown
# Coding Standards

## Code Style
[Formatting, naming conventions, code organization]

## Best Practices
[Development practices, patterns to follow/avoid]

## Testing Requirements
[Unit testing, integration testing, coverage requirements]

## Documentation
[Code documentation, API documentation standards]

## Review Process
[Pull request requirements, review criteria]

## Quality Gates
[Linting, type checking, automated quality checks]
```

### Project Charter Template (workflow/context/project-charter.md)
```markdown
# Project Charter

## Project Mission
[What this project aims to achieve]

## Business Goals
[Business objectives and expected outcomes]

## Technical Goals
[Technical objectives and architectural goals]

## Timeline
[Key milestones and delivery dates]

## Team Structure
[Roles and responsibilities]

## Definition of Done
[Criteria for considering work complete]

## Risk Management
[Identified risks and mitigation strategies]
```

---

## Gitignore Addition

Add these lines to your .gitignore:
```
# Claude Dev Workflow - ignore working files, keep context
workflow/logs/
workflow/scratchpad/
```