#!/usr/bin/env python3
"""
Simple LLM Provider - Supports both Cursor CLI and OpenAI with automatic fallback.
"""

import json
import logging
import subprocess
import os
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

class LLMProvider:
    """Simple LLM provider with Cursor CLI, OpenAI, Anthropic, and Gemini support."""
    
    def __init__(self, preferred_provider="openai"):
        self.preferred_provider = preferred_provider
        self.cursor_available = self._check_cursor_availability()
        self.openai_available = self._check_openai_availability()
        self.anthropic_available = self._check_anthropic_availability()
    
    def _get_active_provider(self) -> str:
        """Determine which provider will be used."""
        if self.preferred_provider == "cursor" and self.cursor_available:
            return "cursor"
        elif self.openai_available:
            return "openai"
        elif self.cursor_available:
            return "cursor"
        else:
            return "none"
    
    def _check_cursor_availability(self) -> bool:
        """Check if Cursor CLI is available and authenticated."""
        try:
            result = subprocess.run(['cursor', 'status'], capture_output=True, text=True, timeout=5)
            return "Not logged in" not in result.stdout
        except Exception:
            return False
    
    def _check_openai_availability(self) -> bool:
        """Check if OpenAI is available."""
        try:
            from openai import OpenAI
            client = OpenAI()
            return True
        except Exception as e:
            logger.debug(f"OpenAI not available: {e}")
            return False

    def _check_anthropic_availability(self) -> bool:
        """Check if Anthropic is available."""
        try:
            import anthropic
            client = anthropic.Anthropic()
            return True
        except Exception as e:
            logger.debug(f"Anthropic not available: {e}")
            return False
    
    def call_llm(self, prompt: str, model: str = None, system_prompt: str = None) -> Dict[str, Any]:
        """
        Call LLM with automatic provider selection and fallback.
        
        Args:
            prompt: User prompt
            model: Model name (optional)
            system_prompt: System prompt (optional)
        
        Returns:
            Dict with response or error
        """
        logger.debug(f"LLM call: model={model}, system_prompt_len={len(system_prompt) if system_prompt else 0}, prompt_len={len(prompt)}")
        
        # Route Claude models to Anthropic
        if model and model.startswith("claude") and self.anthropic_available:
            result = self._call_anthropic(prompt, model, system_prompt)
            if result.get("success"):
                return result
            else:
                logger.warning(f"Anthropic failed: {result.get('error')}, falling back to OpenAI")
        
        # Try preferred provider first
        if self.preferred_provider == "cursor" and self.cursor_available:
            result = self._call_cursor(prompt, model, system_prompt)
            if result.get("success"):
                return result
            else:
                logger.info(f"Cursor CLI failed: {result.get('error', 'Unknown error')}, falling back to OpenAI")
        
        # Fallback to OpenAI (regardless of preferred provider if cursor fails)
        if self.openai_available:
            result = self._call_openai(prompt, model, system_prompt)
            if result.get("success"):
                return result
            else:
                logger.warning(f"OpenAI failed: {result.get('error', 'Unknown error')}")
        
        # Try cursor if OpenAI was preferred but failed
        if self.preferred_provider == "openai" and self.cursor_available:
            result = self._call_cursor(prompt, model, system_prompt)
            if result.get("success"):
                return result
        
        # If both fail, return error with details
        error_msg = "No LLM providers available"
        if not self.cursor_available and not self.openai_available:
            error_msg = "Neither Cursor CLI nor OpenAI is available"
        elif not self.openai_available:
            error_msg = "OpenAI not available (check API key)"
        elif not self.cursor_available:
            error_msg = "Cursor CLI not available (try: cursor login)"
        
        return {
            "success": False,
            "error": error_msg,
            "provider": "none"
        }
    
    def _call_cursor(self, prompt: str, model: str = None, system_prompt: str = None) -> Dict[str, Any]:
        """Call Cursor CLI."""
        try:
            full_prompt = prompt
            if system_prompt:
                full_prompt = f"System: {system_prompt}\n\nIMPORTANT: Your response must be ONLY a valid JSON object. Do not include any explanatory text, markdown formatting, or conversational responses. Start your response directly with {{ and end with }}.\n\nUser: {prompt}"
            
            cmd = ['cursor', 'agent', '--print', '--output-format=json']
            if model:
                cursor_model = self._map_model_to_cursor(model)
                if cursor_model:
                    cmd.extend(['--model', cursor_model])
            cmd.append(full_prompt)
            
            logger.debug(f"Cursor CLI: prompt_len={len(full_prompt)}")
            
            timeout_seconds = 180
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_seconds)
            
            if result.returncode == 0:
                try:
                    response_data = json.loads(result.stdout)
                    return {
                        "success": True,
                        "provider": "cursor",
                        "response": response_data,
                        "raw_output": result.stdout
                    }
                except json.JSONDecodeError:
                    return {
                        "success": True,
                        "provider": "cursor",
                        "response": {"content": result.stdout},
                        "raw_output": result.stdout
                    }
            else:
                return {
                    "success": False,
                    "error": f"Cursor CLI error: {result.stderr}",
                    "provider": "cursor"
                }
                
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": "Cursor CLI timeout",
                "provider": "cursor"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Cursor CLI exception: {str(e)}",
                "provider": "cursor"
            }
    
    def _call_anthropic(self, prompt: str, model: str = None, system_prompt: str = None) -> Dict[str, Any]:
        """Call Anthropic API with streaming."""
        try:
            import anthropic
            client = anthropic.Anthropic()
            
            if not model:
                model = "claude-sonnet-4-20250514"
            
            # Anthropic needs JSON mode via prompt instruction
            sys = system_prompt or ""
            sys += "\n\nIMPORTANT: Respond with ONLY a valid JSON object. No markdown, no explanation."
            
            text_parts = []
            inp_tokens = 0
            out_tokens = 0
            with client.messages.stream(
                model=model,
                max_tokens=16000,
                system=sys,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
            ) as stream:
                for chunk in stream.text_stream:
                    text_parts.append(chunk)
                resp = stream.get_final_message()
                inp_tokens = getattr(resp.usage, "input_tokens", 0)
                out_tokens = getattr(resp.usage, "output_tokens", 0)
            
            content = "".join(text_parts).strip()
            
            cost_info = {
                "input_tokens": inp_tokens,
                "output_tokens": out_tokens,
                "total_tokens": inp_tokens + out_tokens,
                "cost_usd": round((inp_tokens * 3.0 + out_tokens * 15.0) / 1_000_000, 6),
            }
            
            try:
                response_data = json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from markdown code blocks
                import re
                json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', content, re.DOTALL)
                if json_match:
                    response_data = json.loads(json_match.group(1))
                else:
                    response_data = {"content": content}
            
            return {
                "success": True,
                "provider": "anthropic",
                "response": response_data,
                "cost_info": cost_info,
                "model": model,
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"Anthropic error: {str(e)}",
                "provider": "anthropic",
            }

    def _call_openai(self, prompt: str, model: str = None, system_prompt: str = None) -> Dict[str, Any]:
        """Call OpenAI API."""
        try:
            from openai import OpenAI
            client = OpenAI()
            
            if not model:
                model = "gpt-3.5-turbo"
            
            messages = []
            if system_prompt:
                messages.append({"role": "system", "content": system_prompt})
            messages.append({"role": "user", "content": prompt})
            
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.0
            )
            
            content = response.choices[0].message.content
            
            usage = response.usage
            cost_info = {
                "input_tokens": usage.prompt_tokens,
                "output_tokens": usage.completion_tokens,
                "total_tokens": usage.prompt_tokens + usage.completion_tokens,
                "cost_usd": self._calculate_cost(usage.prompt_tokens, usage.completion_tokens, model)
            }
            
            try:
                response_data = json.loads(content)
            except json.JSONDecodeError:
                response_data = {"content": content}
            
            return {
                "success": True,
                "provider": "openai",
                "response": response_data,
                "cost_info": cost_info,
                "model": model
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": f"OpenAI error: {str(e)}",
                "provider": "openai"
            }
    
    def _map_model_to_cursor(self, model: str) -> str:
        """Map OpenAI model names to Cursor model names."""
        mapping = {
            "gpt-4o-mini": "sonnet-4",
            "gpt-4o": "sonnet-4", 
            "gpt-3.5-turbo": "sonnet-4"
        }
        return mapping.get(model, "sonnet-4")
    
    def _calculate_cost(self, input_tokens: int, output_tokens: int, model: str) -> float:
        """Calculate cost based on token usage."""
        pricing = {
            "gpt-3.5-turbo": {"input": 0.0015, "output": 0.002},
            "gpt-4o-mini": {"input": 0.00015, "output": 0.0006},
            "gpt-4o": {"input": 0.005, "output": 0.015}
        }
        
        model_pricing = pricing.get(model, pricing["gpt-3.5-turbo"])
        cost = (input_tokens / 1000 * model_pricing["input"]) + (output_tokens / 1000 * model_pricing["output"])
        return round(cost, 6)
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of all providers."""
        return {
            "cursor_available": self.cursor_available,
            "openai_available": self.openai_available,
            "preferred_provider": self.preferred_provider,
            "active_provider": self._get_active_provider()
        }


def test_llm_provider():
    """Test the LLM provider."""
    print("Testing LLM Provider...")
    
    provider = LLMProvider()
    status = provider.get_status()
    
    print(f"Cursor available: {status['cursor_available']}")
    print(f"OpenAI available: {status['openai_available']}")
    print(f"Active provider: {status['active_provider']}")
    
    result = provider.call_llm("What is 2+2? Respond with just the number.")
    
    if result["success"]:
        print(f"Success with {result['provider']}")
        print(f"Response: {result['response']}")
    else:
        print(f"Failed: {result['error']}")

if __name__ == "__main__":
    test_llm_provider()
