"""
AI Review Engine for project framework
=====================================

True AI-powered review engine that uses actual LLM API calls to generate
contextual, specific feedback based on real document analysis.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional
import requests


class AIReviewEngine:
    """True AI-powered review engine using actual LLM API calls."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize the AI review engine with configuration."""
        self.config = config
        self.mode = "llm"
        
        # Get API configuration
        self.llm_config = config.get("review_modes", {}).get("llm_contextual", {})
        self.providers = self.llm_config.get("providers", [])
        
        # Set up API keys
        self.api_keys = {}
        for provider in self.providers:
            env_var = provider.get("api_key_env")
            if env_var and os.getenv(env_var):
                self.api_keys[provider["name"]] = os.getenv(env_var)
        
    def set_mode(self, mode: str):
        """Set the review mode (for compatibility with framework)."""
        self.mode = mode
        
    def run_reviews(self, phase: str, documents: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run AI-powered reviews for the given phase and documents.
        
        Args:
            phase: Current phase (lfa, work_packages, full_plan)
            documents: Dictionary of processed documents
            
        Returns:
            Review results dictionary with AI-generated content
        """
        results = {
            "mode": "ai_llm",
            "phase": phase,
            "timestamp": datetime.now().isoformat(),
            "reviews": {}
        }
        
        # Analyze the LFA document specifically
        lfa_doc = documents.get('lfa_draft', {})
        if not lfa_doc.get("success", False):
            return results
            
        content = lfa_doc.get('markdown', lfa_doc.get('content', ''))
        
        # Perform true AI analysis
        lfa_analysis = self._ai_analyze_lfa_document(content, documents)
        
        results["reviews"]["lfa_draft"] = lfa_analysis
        
        # Add placeholder reviews for other documents
        for doc_type, doc_data in documents.items():
            if doc_type != 'lfa_draft' and doc_data.get("success", False):
                results["reviews"][doc_type] = {
                    "score": 0,
                    "status": "not_analyzed",
                    "details": f"Document {doc_type} not analyzed in LFA phase"
                }
        
        return results
    
    def _ai_analyze_lfa_document(self, lfa_content: str, all_documents: Dict[str, Any]) -> Dict[str, Any]:
        """Perform true AI analysis of the LFA document."""
        
        # Prepare context for AI analysis
        context = self._prepare_analysis_context(lfa_content, all_documents)
        
        # Generate AI analysis using LLM
        ai_analysis = self._call_llm_for_analysis(context)
        
        return ai_analysis
    
    def _prepare_analysis_context(self, lfa_content: str, all_documents: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare context for AI analysis."""
        
        # Extract call document content for context
        call_doc = all_documents.get('call_document', {})
        call_content = call_doc.get('markdown', '')[:5000]  # Limit for context
        
        # Extract strategy document content for context
        strategy_doc = all_documents.get('strategy_document_1', {})
        strategy_content = strategy_doc.get('markdown', '')[:3000]  # Limit for context
        
        return {
            "lfa_content": lfa_content,
            "call_content": call_content,
            "strategy_content": strategy_content,
            "project_name": "Project",
            "funding_type": "Target Funding Program"
        }
    
    def _call_llm_for_analysis(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Call LLM API to generate true AI analysis."""
        
        # Try different providers in order
        for provider in self.providers:
            provider_name = provider["name"]
            if provider_name in self.api_keys:
                try:
                    if provider_name == "anthropic":
                        return self._call_anthropic_api(context, provider)
                    elif provider_name == "openai":
                        return self._call_openai_api(context, provider)
                except Exception as e:
                    print(f"Failed to call {provider_name}: {e}")
                    continue
        
        # Fallback to simulated AI analysis if no API available
        return self._fallback_ai_analysis(context)
    
    def _call_anthropic_api(self, context: Dict[str, Any], provider: Dict[str, Any]) -> Dict[str, Any]:
        """Call Anthropic Claude API for analysis."""
        
        api_key = self.api_keys["anthropic"]
        model = provider.get("model", "claude-3-sonnet-20240229")
        
        # Prepare the prompt
        prompt = self._create_analysis_prompt(context)
        
        # Make API call
        headers = {
            "x-api-key": api_key,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01"
        }
        
        data = {
            "model": model,
            "max_tokens": 4000,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }
        
        response = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result["content"][0]["text"]
            return self._parse_ai_response(ai_response)
        else:
            raise Exception(f"Anthropic API error: {response.status_code} - {response.text}")
    
    def _call_openai_api(self, context: Dict[str, Any], provider: Dict[str, Any]) -> Dict[str, Any]:
        """Call OpenAI API for analysis."""
        
        api_key = self.api_keys["openai"]
        model = provider.get("model", "gpt-4")
        
        # Prepare the prompt
        prompt = self._create_analysis_prompt(context)
        
        # Make API call
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": 4000,
            "temperature": 0.7
        }
        
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=data,
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            ai_response = result["choices"][0]["message"]["content"]
            return self._parse_ai_response(ai_response)
        else:
            raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
    
    def _create_analysis_prompt(self, context: Dict[str, Any]) -> str:
        """Create a comprehensive prompt for AI analysis."""
        
        return f"""
You are an expert LFA (Logical Framework Analysis) consultant for research funding proposals. Please analyze the following LFA document and provide a comprehensive assessment.

**PROJECT CONTEXT:**
- Project: {context['project_name']}
- Funding Type: {context['funding_type']}

**LFA DOCUMENT TO ANALYZE:**
{context['lfa_content']}

**CALL DOCUMENT CONTEXT (for alignment analysis):**
{context['call_content']}

**STRATEGY DOCUMENT CONTEXT (for policy alignment):**
{context['strategy_content']}

**ANALYSIS REQUIREMENTS:**

Please provide a comprehensive LFA analysis in the following JSON format:

{{
    "overall_score": <number between 0-100>,
    "overall_rating": "<EXCELLENT/GOOD/FAIR/POOR>",
    "executive_summary": "<detailed narrative summary of LFA quality>",
    "lfa_analysis": {{
        "goal_quality": {{
            "score": <number>,
            "rating": "<rating>",
            "details": "<specific analysis of goal quality>",
            "criteria": {{
                "aspirational_framing": {{"score": <number>, "rating": "<rating>", "comments": "<specific feedback>"}},
                "beneficiary_identification": {{"score": <number>, "rating": "<rating>", "comments": "<specific feedback>"}},
                "scope_appropriateness": {{"score": <number>, "rating": "<rating>", "comments": "<specific feedback>"}},
                "eu_policy_alignment": {{"score": <number>, "rating": "<rating>", "comments": "<specific feedback>"}}
            }},
            "strengths": ["<specific strength 1>", "<specific strength 2>", "<specific strength 3>"],
            "improvements": ["<specific improvement 1>", "<specific improvement 2>", "<specific improvement 3>"]
        }},
        "purpose_quality": {{
            "score": <number>,
            "rating": "<rating>",
            "details": "<specific analysis of purpose quality>",
            "criteria": {{
                "change_description": {{"score": <number>, "rating": "<rating>", "comments": "<specific feedback>"}},
                "measurability": {{"score": <number>, "rating": "<rating>", "comments": "<specific feedback>"}},
                "connection_to_results": {{"score": <number>, "rating": "<rating>", "comments": "<specific feedback>"}},
                "realistic_scope": {{"score": <number>, "rating": "<rating>", "comments": "<specific feedback>"}}
            }},
            "strengths": ["<specific strength 1>", "<specific strength 2>"],
            "improvements": ["<specific improvement 1>", "<specific improvement 2>"]
        }},
        "results_quality": {{
            "score": <number>,
            "rating": "<rating>",
            "details": "<specific analysis of results quality>",
            "criteria": {{
                "concrete_deliverables": {{"score": <number>, "rating": "<rating>", "comments": "<specific feedback>"}},
                "logical_flow": {{"score": <number>, "rating": "<rating>", "comments": "<specific feedback>"}},
                "measurable_indicators": {{"score": <number>, "rating": "<rating>", "comments": "<specific feedback>"}},
                "market_relevance": {{"score": <number>, "rating": "<rating>", "comments": "<specific feedback>"}}
            }},
            "strengths": ["<specific strength 1>", "<specific strength 2>"],
            "improvements": ["<specific improvement 1>", "<specific improvement 2>"]
        }},
        "activities_quality": {{
            "score": <number>,
            "rating": "<rating>",
            "details": "<specific analysis of activities quality>",
            "criteria": {{
                "action_oriented_language": {{"score": <number>, "rating": "<rating>", "comments": "<specific feedback>"}},
                "resource_awareness": {{"score": <number>, "rating": "<rating>", "comments": "<specific feedback>"}},
                "methodology_clarity": {{"score": <number>, "rating": "<rating>", "comments": "<specific feedback>"}},
                "feasibility": {{"score": <number>, "rating": "<rating>", "comments": "<specific feedback>"}}
            }},
            "strengths": ["<specific strength 1>", "<specific strength 2>"],
            "improvements": ["<specific improvement 1>", "<specific improvement 2>"]
        }},
        "logical_coherence": {{
            "score": <number>,
            "rating": "<rating>",
            "details": "<specific analysis of logical coherence>",
            "criteria": {{
                "causal_relationships": <number>,
                "assumption_analysis": <number>
            }}
        }},
        "call_alignment": {{
            "score": <number>,
            "rating": "<rating>",
            "details": "<specific analysis of call alignment>",
            "criteria": {{
                "seaweed_bioeconomy": <number>,
                "innovation_focus": <number>,
                "sustainability": <number>,
                "market_readiness": <number>,
                "eu_priorities": <number>,
                "collaboration": <number>
            }}
        }}
    }},
    "recommendations": {{
        "high_priority": ["<specific recommendation 1>", "<specific recommendation 2>", "<specific recommendation 3>"],
        "medium_priority": ["<specific recommendation 1>", "<specific recommendation 2>"],
        "low_priority": ["<specific recommendation 1>", "<specific recommendation 2>"]
    }},
    "ai_content": {{
        "executive_summary": "<detailed AI-generated executive summary>",
        "key_findings": {{
            "strongest_section": "<section name> - <score>% - <reason>",
            "improvement_needed": "<section name> - <score>% - <reason>",
            "critical_gap": "<specific critical gap identified>",
            "innovation_highlight": "<specific innovation highlight>"
        }},
        "strengths": ["<AI-generated strength 1>", "<AI-generated strength 2>", "<AI-generated strength 3>"],
        "improvements": ["<AI-generated improvement 1>", "<AI-generated improvement 2>", "<AI-generated improvement 3>"]
    }}
}}

**IMPORTANT INSTRUCTIONS:**
1. Base your analysis on the ACTUAL CONTENT of the LFA document
2. Provide SPECIFIC, CONTEXTUAL feedback - not generic templates
3. Reference specific elements from the document in your analysis
4. Generate UNIQUE content that reflects the actual document quality
5. Be realistic in scoring - not everything should be excellent
6. Provide actionable, specific recommendations
7. Ensure all content is AI-generated and contextual to this specific LFA

Please provide your analysis in valid JSON format only.
"""
    
    def _parse_ai_response(self, ai_response: str) -> Dict[str, Any]:
        """Parse AI response and extract structured data."""
        
        try:
            # Try to extract JSON from the response
            if "```json" in ai_response:
                json_start = ai_response.find("```json") + 7
                json_end = ai_response.find("```", json_start)
                json_str = ai_response[json_start:json_end].strip()
            elif "```" in ai_response:
                json_start = ai_response.find("```") + 3
                json_end = ai_response.find("```", json_start)
                json_str = ai_response[json_start:json_end].strip()
            else:
                json_str = ai_response.strip()
            
            # Parse JSON
            analysis = json.loads(json_str)
            
            # Add metadata
            analysis["score"] = analysis.get("overall_score", 0)
            analysis["status"] = analysis.get("overall_rating", "unknown").lower()
            analysis["details"] = analysis.get("executive_summary", "")
            
            return analysis
            
        except json.JSONDecodeError as e:
            print(f"Failed to parse AI response as JSON: {e}")
            return self._fallback_ai_analysis({"lfa_content": ai_response})
    
    def _fallback_ai_analysis(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """Fallback analysis when AI API is not available."""
        
        return {
            "score": 75,
            "status": "good",
            "details": "AI analysis not available - using fallback assessment",
            "lfa_analysis": {
                "goal_quality": {"score": 70, "rating": "good", "details": "Fallback analysis"},
                "purpose_quality": {"score": 75, "rating": "good", "details": "Fallback analysis"},
                "results_quality": {"score": 80, "rating": "good", "details": "Fallback analysis"},
                "activities_quality": {"score": 70, "rating": "good", "details": "Fallback analysis"},
                "logical_coherence": {"score": 75, "rating": "good", "details": "Fallback analysis"},
                "call_alignment": {"score": 80, "rating": "good", "details": "Fallback analysis"}
            },
            "recommendations": {
                "high_priority": ["Enable AI analysis for detailed assessment"],
                "medium_priority": ["Configure API keys for LLM access"],
                "low_priority": ["Review fallback analysis results"]
            },
            "ai_content": {
                "executive_summary": "Fallback analysis - AI API not available",
                "key_findings": {
                    "strongest_section": "Results Quality - 80% - Fallback analysis",
                    "improvement_needed": "Goal Quality - 70% - Fallback analysis",
                    "critical_gap": "AI analysis not available",
                    "innovation_highlight": "Fallback assessment mode"
                },
                "strengths": ["Fallback analysis available", "Basic assessment completed"],
                "improvements": ["Enable AI analysis", "Configure API access"]
            }
        }
