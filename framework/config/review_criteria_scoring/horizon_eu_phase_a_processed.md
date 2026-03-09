# Phase A: LFA Analysis - Unified Review Criteria & Output Template
**Phase**: A (Logic Framework Analysis)  
**Purpose**: Comprehensive LFA assessment with integrated output template structure

---

## Review Framework Structure

This document defines both the **evaluation criteria** and the **output template structure** in a unified format. The criteria drive the analysis, and the template structure defines how results are presented.

---

## 1. Call Alignment (Weight: 30%)

**Key Question**: Does the LFA respond to what the call is asking for?

### Sub-Criteria

#### CA1: Call Objectives (20% of Call Alignment)
- **Check**: Do objectives explicitly address call objectives?
- **Method**: Key terms and phrases from call summary appear in proposal objectives
- **Evidence**: Direct quotes, semantic similarity analysis
- **Template Placeholder**: `{{CA1_SCORE}}`, `{{CA1_STATUS}}`, `{{CA1_FEEDBACK}}`

#### CA2: Scope Fit (20% of Call Alignment)
- **Check**: Do activities fit within call scope (mandatory elements included, none out-of-scope)?
- **Method**: Activity mapping, compliance verification
- **Evidence**: Scope compliance matrix, out-of-scope detection
- **Template Placeholder**: `{{CA2_SCORE}}`, `{{CA2_STATUS}}`, `{{CA2_FEEDBACK}}`

#### CA3: Outcomes & Impacts (20% of Call Alignment)
- **Check**: Are expected results aligned with listed outcomes/impacts in the call?
- **Method**: Semantic similarity between proposal outcomes and call outcomes
- **Evidence**: Outcome mapping, gap analysis
- **Template Placeholder**: `{{CA3_SCORE}}`, `{{CA3_STATUS}}`, `{{CA3_FEEDBACK}}`

#### CA4: Evaluation Criteria Coverage (15% of Call Alignment)
- **Check**: Are all Horizon evaluation categories (Excellence, Impact, Implementation) addressed?
- **Method**: Coverage matrix analysis
- **Evidence**: Missing criteria highlights, coverage report
- **Template Placeholder**: `{{CA4_SCORE}}`, `{{CA4_STATUS}}`, `{{CA4_FEEDBACK}}`

#### CA5: Eligibility & Formalities (15% of Call Alignment)
- **Check**: Partners, TRL, budget, duration comply with requirements?
- **Method**: Compare project metadata against call rules
- **Evidence**: Compliance checklist, requirement verification
- **Template Placeholder**: `{{CA5_SCORE}}`, `{{CA5_STATUS}}`, `{{CA5_FEEDBACK}}`

#### CA6: Terminology Alignment (10% of Call Alignment)
- **Check**: Does the proposal use call-expected terms and keywords?
- **Method**: Glossary alignment between call document and proposal text
- **Evidence**: Terminology analysis, consistency report
- **Template Placeholder**: `{{CA6_SCORE}}`, `{{CA6_STATUS}}`, `{{CA6_FEEDBACK}}`

---

## 2. LFA Internal Consistency (Weight: 50%)

**Key Question**: Does the LFA follow proper logical framework structure and internal logic?

### Sub-Criteria

#### LC1: Hierarchy Coherence (20% of LFA Consistency)
- **Check**: Goal → Purpose → Outcomes logically connected
- **Method**: Semantic similarity using embeddings/TF-IDF
- **Evidence**: Coherence mapping, logical flow analysis
- **Template Placeholder**: `{{LC1_SCORE}}`, `{{LC1_STATUS}}`, `{{LC1_FEEDBACK}}`

#### LC2: Traceability (20% of LFA Consistency)
- **Check**: Outcomes ↔ Outputs ↔ Tasks ↔ Deliverables consistently mapped
- **Method**: Validate references in normalized LFA structure
- **Evidence**: Traceability matrix, orphan item detection
- **Template Placeholder**: `{{LC2_SCORE}}`, `{{LC2_STATUS}}`, `{{LC2_FEEDBACK}}`

#### LC3: KPI SMARTness (15% of LFA Consistency)
- **Check**: Indicators are specific, measurable, time-bound, with baseline/target
- **Method**: Regex/field presence checks over KPI objects
- **Evidence**: SMART criteria compliance report
- **Template Placeholder**: `{{LC3_SCORE}}`, `{{LC3_STATUS}}`, `{{LC3_FEEDBACK}}`

#### LC4: Temporal Coherence (10% of LFA Consistency)
- **Check**: Deliverables/milestones fit within project timeframe and WP/Task windows
- **Method**: Date validation with project timeline
- **Evidence**: Timeline coherence analysis
- **Template Placeholder**: `{{LC4_SCORE}}`, `{{LC4_STATUS}}`, `{{LC4_FEEDBACK}}`

#### LC5: Risk Linkage & Mitigation (10% of LFA Consistency)
- **Check**: Risks linked to outputs/tasks, with clear mitigation actions
- **Method**: Ensure each Risk has links to specific IDs and mitigation text
- **Evidence**: Risk-mitigation mapping matrix
- **Template Placeholder**: `{{LC5_SCORE}}`, `{{LC5_STATUS}}`, `{{LC5_FEEDBACK}}`

#### LC6: Terminology Consistency (10% of LFA Consistency)
- **Check**: Key terms/glossary applied consistently throughout
- **Method**: Lemmatize with spaCy; compare against glossary
- **Evidence**: Terminology consistency report
- **Template Placeholder**: `{{LC6_SCORE}}`, `{{LC6_STATUS}}`, `{{LC6_FEEDBACK}}`

#### LC7: Duplication & Overlap (7.5% of LFA Consistency)
- **Check**: No redundant or overlapping outcomes/outputs/tasks
- **Method**: Near-duplicate detection using similarity analysis
- **Evidence**: Duplication detection report
- **Template Placeholder**: `{{LC7_SCORE}}`, `{{LC7_STATUS}}`, `{{LC7_FEEDBACK}}`

#### LC8: Structural Completeness (7.5% of LFA Consistency)
- **Check**: All required LFA elements present and logically ordered
- **Method**: Validate presence/word-count thresholds per section
- **Evidence**: Structure completeness checklist
- **Template Placeholder**: `{{LC8_SCORE}}`, `{{LC8_STATUS}}`, `{{LC8_FEEDBACK}}`

---

## 3. Content Quality & Readability (Weight: 20%)

**Key Question**: Is the content clear, specific, and well-written?

### Sub-Criteria

#### CQ1: Readability & Clarity (40% of Content Quality)
- **Check**: Clear, jargon-controlled, easy for evaluators to follow
- **Method**: Readability indices (Flesch, SMOG); jargon detection
- **Evidence**: Readability score report, clarity assessment
- **Template Placeholder**: `{{CQ1_SCORE}}`, `{{CQ1_STATUS}}`, `{{CQ1_FEEDBACK}}`

#### CQ2: Specificity & Measurability (30% of Content Quality)
- **Check**: Objectives and outputs concrete and measurable
- **Method**: Quantitative indicator detection; specificity vs. vagueness ratio
- **Evidence**: Specificity analysis, measurability report
- **Template Placeholder**: `{{CQ2_SCORE}}`, `{{CQ2_STATUS}}`, `{{CQ2_FEEDBACK}}`

#### CQ3: Professional Writing Quality (20% of Content Quality)
- **Check**: Grammar, formatting, and tone professional
- **Method**: Grammar/spell checking; style consistency analysis
- **Evidence**: Writing quality report, style consistency check
- **Template Placeholder**: `{{CQ3_SCORE}}`, `{{CQ3_STATUS}}`, `{{CQ3_FEEDBACK}}`

#### CQ4: Terminology Consistency (10% of Content Quality)
- **Check**: Same term used consistently across sections
- **Method**: Term frequency analysis; consistency checking
- **Evidence**: Terminology usage report
- **Template Placeholder**: `{{CQ4_SCORE}}`, `{{CQ4_STATUS}}`, `{{CQ4_FEEDBACK}}`

---

## 4. Scoring & Readiness Levels

### Overall Calculation
**Formula**: (Call Alignment × 30%) + (LFA Internal Consistency × 50%) + (Content Quality × 20%)

### Readiness Levels (for each area + overall)

#### Level 5: Excellent (85-100%)
- **Description**: All/most criteria fully met with strong evidence
- **Action**: Ready for next phase

#### Level 4: Strong (70-84%)
- **Description**: Minor gaps, mostly well addressed
- **Action**: Minor improvements recommended

#### Level 3: Adequate (55-69%)
- **Description**: Several gaps need fixing before next phase
- **Action**: Focused improvements needed

#### Level 2: Weak (40-54%)
- **Description**: Major inconsistencies or missing parts
- **Action**: Significant rework required

#### Level 1: Poor (0-39%)
- **Description**: Minimal compliance, needs major rework
- **Action**: Major restructuring needed

---

## 5. AI-Generated Comments Requirement

**Critical Requirement**: For each criterion, the system must generate detailed, contextual comments that:

1. **Explain the score** - Why this specific score was assigned
2. **Provide evidence** - What specific content or lack thereof led to this assessment
3. **Give actionable feedback** - Specific recommendations for improvement
4. **Be contextual** - Comments should reference actual content from the LFA document
5. **Be professional** - Written in evaluation panel-appropriate language

**Example of good AI-generated comment**:
> "The LFA demonstrates strong logical hierarchy with clear connections between the overall goal of 'sustainable maritime bridge technologies' and the project purpose of 'bridging critical gaps in the European seaweed value chain.' However, the connection between individual outcomes and the project purpose could be strengthened with more explicit causal language. Recommendation: Add 'leads to' or 'contributes to' statements linking each outcome to the project purpose."

This unified approach ensures that:
- **Criteria definition** drives the analysis
- **Template structure** is automatically generated from criteria
- **No duplication** between criteria and template files
- **Consistent evaluation** across all assessments
- **Detailed AI feedback** for each criterion
