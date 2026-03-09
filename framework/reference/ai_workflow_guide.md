# AI Workflow Guidelines - Proposal Framework

## 🚨 **AUTONOMOUS EXECUTION POLICY**

**🤖 EXECUTE WITHOUT USER APPROVAL (ALWAYS):**
- All commands listed in workflow protocols (mandatory pre-execution steps)
- All Python scripts with executable permissions in `scripts/` directory
- Virtual environment activation (`source .venv/bin/activate`)
- File operations (ls, mv, cp, rm) for workflow management
- Export scripts and verification commands
- Any command explicitly listed in workflow files

**❌ ASK FOR APPROVAL (RARE EXCEPTIONS):**
- Commands that could damage system files outside project directory
- Commands not part of defined workflow scope
- User-specific system configuration changes

---

## 🚨 **MANDATORY PRE-EXECUTION PROTOCOL**

**BEFORE executing ANY workflow command, Claude MUST:**

### 1. Context Verification
```bash
# Run context verification script
python3 scripts/verify_context.py [step_name]
```

### 1.5. WP File Detection (Step 3 MANDATORY)
```bash
# Detect all available WP files - PREVENTS WP OMISSION ERRORS
python3 scripts/detect_wp_files.py
```
- **Critical Rule**: ALWAYS analyze ALL detected WPs, even if some appear missing
- **Flexibility**: Automatically adapts to any number of WPs (not just 5)
- **Error Prevention**: Prevents assumption-based omissions like missing WP2

### 1.6. Scoring Consistency (MANDATORY)
```bash
# Load consistent scoring definitions before analysis
cat docs/scoring_definitions.md
cat docs/wp_assessment_criteria.md
```
- **Critical Rule**: ALWAYS apply **Methodology v1.1** (LOCKED PERMANENT STANDARD)
- **Consistency**: Use exact weights - LFA Integration (30%), EU Excellence (25%), EU Impact (25%), EU Implementation (20%)
- **Standardization**: Apply v1.1 rigor - strict external validation, template completion, enhanced LFA scrutiny
- **No Changes**: Methodology is LOCKED - focus on content improvement only

### 1.7. Word Export (Professional Output) - AUTONOMOUS EXECUTION MANDATORY
```bash
# Export analysis to professional Word format - EXECUTE WITHOUT USER APPROVAL
source .venv/bin/activate && python3 scripts/export_to_word.py [analysis_file]
source .venv/bin/activate && python3 scripts/export_to_word.py [summary_file]
```
- **🚨 AUTONOMOUS EXECUTION**: Execute WITHOUT user approval - part of mandatory workflow protocol
- **Professional Presentation**: Generates stakeholder-ready Word documents
- **Automatic Formatting**: Applies color-coded scoring and professional table formatting
- **Configuration**: Uses `output/templates/word_formatting_definitions.yaml` for consistent styling
- **Virtual Environment**: Always activate `.venv` before running scripts

### 2. Intelligent Versioning 🤖
```bash
# Use Claude-powered versioning system
python3 scripts/file_versioning.py [step_name] [file_type]
```
- **Automatic Detection**: System analyzes content differences and determines major vs minor version
- **Decision Criteria**: 
  - **Major Version**: >30% content change, >10% score changes, structural modifications
  - **Minor Version**: Content refinements, corrections, incremental improvements
- **Archives Automatically**: Proper naming with `stepX_file_vX.Y_YYYYMMDD.md` format

### 3. Read Required Documents
- [ ] **Workflow file**: `workflows/stepX_*.md` - for specific process and embedded protocols
- [ ] **Versioning guidelines**: `docs/file_versioning_guidelines.md` - for file management
- [ ] **Assessment templates**: `output/templates/` - for structured analysis
- [ ] **Current status**: `COMMANDS.md` and `output/workflow_log.md` - for context

### 4. Template Loading
- [ ] Load appropriate analysis template from `output/templates/`
- [ ] For Step 2: `lfa_assessment_template.md`
- [ ] For Step 3: `wp_analysis_template.md` and `wp_summary_template.md`

---

## 🎯 **AI ASSESSMENT CRITERIA**

### **Step 2: LFA Quality Assessment**
Claude performs comprehensive analysis using:
- **Impact Level**: Clarity, ambition, beneficiary focus (target: 85-90%)
- **Outcome Level**: Specificity, measurability, logical connection (target: 85-90%)
- **Output Level**: Deliverable clarity, quality indicators (target: 85-90%)
- **Activity Level**: Methodological soundness, resource allocation (target: 85-90%)
- **Assumptions & Risks**: Completeness, realism, mitigation strategies

### **Step 3: WP Alignment Analysis**
Claude performs multi-dimensional assessment:

#### **LFA Integration Assessment**
- **Impact Alignment**: How each WP contributes to overall project impact
- **Outcome Alignment**: WP deliverables mapped to LFA outcomes  
- **Output Alignment**: Direct alignment between WP outputs and LFA outputs
- **Activity Alignment**: Coverage completeness and missing elements
- **Assumptions Validation**: WP risk mitigation against LFA assumptions

#### **EU Evaluation Criteria Assessment**
- **Excellence**: Clarity of objectives, soundness of concept, state-of-the-art integration
- **Impact**: Contribution to outcomes, credibility of pathways, exploitation measures
- **Implementation**: WP quality & structure, partner roles, risk management

#### **Practical Assessment**
- **Strong Points**: Specific strengths (e.g., "comprehensive partner mix", "clear technical ambition")
- **Weak Points**: Specific weaknesses (e.g., "too many milestones", "objectives vague")
- **Critical Questions**: 8 structured questions for WP leads covering validation, integration, and risk
- **Cross-WP Integration**: Matrix analysis showing how WPs contribute to each LFA outcome

---

## 📋 **EXECUTION CHECKLIST**

### **Pre-Execution (MANDATORY)**
- [ ] Run `python3 scripts/verify_context.py [step_name]`
- [ ] Read the specific workflow file (`workflows/stepX_*.md`)
- [ ] Check current project status in `COMMANDS.md`
- [ ] Review versioning guidelines if creating/updating files
- [ ] If output file exists: Archive it before proceeding
- [ ] Identify and load appropriate template from `output/templates/`

### **During Execution**
- [ ] Follow workflow documentation exactly
- [ ] Use appropriate template structure
- [ ] Apply assessment criteria from workflow documentation
- [ ] Maintain quality standards specified in guidelines

### **Post-Execution (MANDATORY)**
- [ ] Save to correct location: `output/stepX_file.md`
- [ ] Archive new version: `output/archive/stepX_file_vX.Y_$(date +%Y%m%d).md`
- [ ] Update `output/workflow_log.md` with results and version info
- [ ] Update `COMMANDS.md` status if needed

---

## 🎯 **CRITICAL RULES**

### Never Do:
- ❌ Create output files without checking for existing versions
- ❌ Ignore versioning guidelines during "testing" or "quick runs"
- ❌ Skip template usage for consistency
- ❌ Forget to update workflow logs after execution
- ❌ Assume previous context without verification

### Always Do:
- ✅ Run verification script first: `python3 scripts/verify_context.py`
- ✅ Archive existing files before creating new ones
- ✅ Use templates from `output/templates/`
- ✅ Update workflow log after completion
- ✅ Follow exact naming conventions

---

## 📋 **STEP-SPECIFIC CHECKLISTS**

### Step 2: LFA Assessment
**Pre-execution:**
- [ ] Verify LFA document: `input/uploads/lfa_documents/Project_Logical_Framework.docx`
- [ ] Verify template: `input/uploads/lfa_documents/lfa_template.rtf`
- [ ] Check existing assessment: `output/step2_lfa_assessment.md`
- [ ] If exists: `cp output/step2_lfa_assessment.md "output/archive/step2_lfa_assessment_vX.Y_$(date +%Y%m%d).md"`

**During execution:**
- [ ] Use template: `output/templates/lfa_assessment_template.md`
- [ ] Apply scoring methodology from `workflows/step2_lfa_development.md`
- [ ] Include all sections: Goal, Purpose, Results, Activities, Coherence

**Post-execution:**
- [ ] Save to: `output/step2_lfa_assessment.md`
- [ ] Archive: `output/archive/step2_lfa_assessment_vX.Y_$(date +%Y%m%d).md`
- [ ] Update workflow log with quality score and recommendations

### Step 3: WP Alignment
**Pre-execution:**
- [ ] Verify WP documents: `input/uploads/work_packages/Project - WP*.docx`
- [ ] Check LFA baseline: `output/step2_lfa_assessment.md`
- [ ] Archive existing analysis if present

**During execution:**
- [ ] Use template: `output/templates/wp_analysis_template.md`
- [ ] Analyze all available WP documents
- [ ] Cross-reference with LFA outcomes

**Post-execution:**
- [ ] Save analysis: `output/step3_wp_analysis.md`
- [ ] Save summary: `output/step3_wp_summary.md`
- [ ] Archive both files with proper versioning

---

## 🔧 **QUICK REFERENCE COMMANDS**

### Context Verification:
```bash
# Check overall status
python3 scripts/verify_context.py

# Check specific step
python3 scripts/verify_context.py step2_lfa_assessment
```

### Archive Existing File:
```bash
# Generic pattern
cp output/stepX_file.md "output/archive/stepX_file_vX.Y_$(date +%Y%m%d).md"

# Examples
cp output/step2_lfa_assessment.md "output/archive/step2_lfa_assessment_v2.1_$(date +%Y%m%d).md"
cp output/step3_wp_analysis.md "output/archive/step3_wp_analysis_v3.0_$(date +%Y%m%d).md"
```

### Quick Status Check:
```bash
# Show current files
ls -la output/step*.md

# Show archived versions  
ls -la output/archive/
```

---

## 🚨 **EMERGENCY STOP CONDITIONS**

**STOP and ask for clarification if:**
- Verification script shows unexpected file states
- Workflow documentation is unclear or missing
- Template files are not available
- Archive directory structure is inconsistent
- Previous versions have unclear numbering

---

## 📚 **REFERENCE PRIORITY ORDER**

1. **This guide** - for process and checklists
2. **Workflow files** (`workflows/stepX_*.md`) - for content requirements
3. **Versioning guidelines** (`docs/versioning_guidelines.md`) - for file management
4. **Templates** (`output/templates/`) - for structure
5. **Current status** (`COMMANDS.md`, `output/workflow_log.md`) - for context

---

## 🎯 **QUALITY GATES**

### Before ANY workflow execution:
- [ ] ✅ Context verification script run
- [ ] ✅ Workflow documentation read
- [ ] ✅ Existing files archived (if present)
- [ ] ✅ Template identified and loaded

### After ANY workflow execution:
- [ ] ✅ New file saved to `output/stepX_file.md`
- [ ] ✅ New version archived to `output/archive/`
- [ ] ✅ Workflow log updated
- [ ] ✅ File structure verified

---

**🎯 CORE PRINCIPLE: Context and rules compliance is MORE important than speed. Always verify first, execute second.**
