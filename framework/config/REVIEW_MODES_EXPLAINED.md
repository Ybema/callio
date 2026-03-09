# Review Modes Explained 🔍

**SINGLE SOURCE OF TRUTH** - This document explains what happens when you choose different review modes in the ProposalFramework.

All mode selection references point here for consistency and easy maintenance.

## 🚀 Quick Reference

| Mode | Command | Best For | Cost | Time | Internet |
|------|---------|----------|------|------|----------|
| 🤖 **Python** | `--mode python` | Development, iteration | FREE | Seconds | No |
| 🧠 **LLM** | `--mode llm` | Final review, strategy | $0.10-$0.50 | 30-60s | Yes |

**💡 Recommended workflow:** Use Python during development → LLM for final review

---

## 🤖 Python Mode vs 🧠 LLM Mode

### 🤖 **Python Mode** (`--mode python`)

**What it does:** Uses specialized Python libraries to analyze your documents with mathematical precision.

**How it works:**
1. **Text Similarity Analysis**
   - Compares your LFA against call requirements using TF-IDF vectors (keyword matching)
   - Measures semantic similarity using AI embeddings (meaning matching)  
   - Fuzzy matches headings and key terms (flexible text matching)

2. **Quality Checks**
   - **Readability**: Calculates Flesch reading scores, grade levels
   - **Language Quality**: Spell checks, grammar validation
   - **Structure**: Verifies required sections, heading hierarchy
   - **Logic**: Checks cross-references, dependency graphs

3. **Evidence-Based Scoring**
   - Each score comes with specific evidence from your text
   - Shows exactly which sections scored well/poorly
   - Provides mathematical confidence levels

**Advantages:**
- ✅ **Consistent**: Same input = same output, every time
- ✅ **Fast**: Processes documents in seconds
- ✅ **Transparent**: Shows exactly how scores are calculated
- ✅ **Offline**: Works without internet connection
- ✅ **Cost-Free**: No API costs
- ✅ **Detailed Evidence**: Points to specific text that supports each score

**Best for:**
- Regular quality checks during document development
- Consistent scoring across multiple proposals
- When you need detailed, traceable analysis
- Budget-conscious projects

---

### 🧠 **LLM Mode** (`--mode llm`)

**What it does:** Uses advanced AI language models (like ChatGPT/Claude) to read and understand your documents like a human expert would.

**How it works:**
1. **Contextual Understanding**
   - Reads your entire LFA as a coherent story
   - Understands complex relationships between goals, outcomes, activities
   - Grasps nuanced meaning and implicit connections

2. **Expert-Level Analysis**
   - Provides strategic recommendations like a consultant would
   - Identifies subtle alignment issues with call requirements
   - Suggests specific improvements in natural language

3. **Holistic Assessment**
   - Considers the "big picture" coherence
   - Evaluates narrative flow and logical progression
   - Assesses stakeholder perspective and market relevance

**Advantages:**
- ✅ **Human-Like**: Understands context, nuance, and implicit meaning
- ✅ **Strategic**: Provides high-level insights and recommendations
- ✅ **Flexible**: Adapts analysis style to different proposal types
- ✅ **Comprehensive**: Considers factors that rule-based systems might miss

**Limitations:**
- ⚠️ **Variable**: Results may vary slightly between runs
- ⚠️ **Slower**: Takes longer to process (30-60 seconds per document)
- ⚠️ **Cost**: Uses API credits (typically $0.10-$0.50 per analysis)
- ⚠️ **Internet Required**: Needs connection to AI service
- ⚠️ **Less Traceable**: Harder to see exactly why specific scores were given

**Best for:**
- Final quality review before submission
- Strategic assessment of proposal coherence
- When you need expert-level insights
- Complex proposals with nuanced requirements

---

## 🎯 **Which Mode Should You Choose?**

### **During Development: Python Mode**
Use `--mode python` when:
- Writing and refining your LFA
- Checking for basic quality issues
- Need quick feedback on structure and alignment
- Want to track improvement over multiple iterations

### **Before Submission: LLM Mode**
Use `--mode llm` when:
- Your LFA is nearly complete
- Need strategic, expert-level review
- Want human-like assessment of coherence
- Preparing for final submission

### **Best Practice: Use Both! 🚀**
1. **Start with Python** during development for fast, consistent feedback
2. **Finish with LLM** for final strategic review and polish

---

## 📊 **Output Differences**

### Python Mode Output:
```
Goal Quality: 85% (Good)
- Keyword alignment: 82%
- Semantic similarity: 88% 
- Evidence: "The goal clearly states 'sustainable innovation in marine biotechnology' 
  which matches call requirement 3.2 on blue economy innovation"
```

### LLM Mode Output:
```
Goal Quality: 87% (Good)
"The goal effectively articulates a compelling vision for sustainable marine 
biotechnology innovation. However, it could be strengthened by explicitly 
connecting to the EU's Blue Deal strategy and quantifying expected societal 
impact. Consider adding specific metrics for environmental benefits."
```

---

## ⚙️ **Technical Details**

### Python Mode Libraries:
- **rapidfuzz**: Fuzzy text matching
- **scikit-learn**: TF-IDF similarity analysis  
- **sentence-transformers**: Semantic embeddings
- **textstat**: Readability analysis
- **spacy**: Language processing
- **networkx**: Dependency analysis

### LLM Mode Providers:
- **Claude 4 Sonnet** (Anthropic): Best for detailed analysis
- **GPT-4** (OpenAI): Good for strategic insights
- **Custom prompts**: Tailored for proposal evaluation

---

## 💡 **Quick Start Examples**

```bash
# Fast development feedback
python run_phase_a.py --mode python --funding-type horizon_eu

# Strategic final review  
python run_phase_a.py --mode llm --funding-type horizon_eu

# Compare both approaches
python run_phase_a.py --mode python --funding-type horizon_eu
python run_phase_a.py --mode llm --funding-type horizon_eu
```

Choose the mode that fits your current needs and budget! 🎯
