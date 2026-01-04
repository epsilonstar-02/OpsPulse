#!/usr/bin/env python
"""
OpsPulse AI - Integration Test Script

Quick test to verify all components are working:
1. Test DeepSeek LLM directly
2. Test RAG server endpoint
3. Test end-to-end remediation query

Usage:
    python test_integration.py
"""

import sys
import httpx
import json

RAG_URL = "http://localhost:5000"
DEEPSEEK_URL = "http://34.171.226.157:8080"


def test_deepseek_direct():
    """Test DeepSeek LLM directly."""
    print("\n" + "="*60)
    print("🔬 Test 1: DeepSeek LLM Direct Connection")
    print("="*60)
    
    try:
        import litellm
        
        print(f"   Connecting to {DEEPSEEK_URL}...")
        response = litellm.completion(
            model='openai/unsloth/DeepSeek-R1-Distill-Qwen-1.5B-GGUF:Q4_K_M',
            messages=[{'role': 'user', 'content': 'Say hello in 5 words'}],
            api_base=f'{DEEPSEEK_URL}/v1',
            api_key='not-needed',
            timeout=60,
            max_tokens=200,
        )
        
        msg = response.choices[0].message
        content = msg.content or ""
        reasoning = getattr(msg, 'reasoning_content', "")
        
        print(f"   ✓ Response received!")
        print(f"   Content: {repr(content[:100]) if content else '(empty)'}")
        print(f"   Reasoning: {reasoning[:100] if reasoning else '(none)'}...")
        
        if content or reasoning:
            print("   ✅ DeepSeek LLM: PASS")
            return True
        else:
            print("   ❌ DeepSeek LLM: FAIL (no content)")
            return False
            
    except Exception as e:
        print(f"   ❌ DeepSeek LLM: FAIL ({e})")
        return False


def test_rag_health():
    """Test RAG server health endpoint."""
    print("\n" + "="*60)
    print("🔬 Test 2: RAG Server Health Check")
    print("="*60)
    
    try:
        with httpx.Client(timeout=10.0) as client:
            print(f"   Connecting to {RAG_URL}/health...")
            response = client.get(f"{RAG_URL}/health")
            
            if response.status_code == 200:
                print(f"   ✓ Health: {response.json()}")
                
                # Get stats
                stats = client.get(f"{RAG_URL}/stats").json()
                print(f"   ✓ Documents: {stats.get('total_documents', 0)}")
                print(f"   ✓ LLM Model: {stats.get('llm_model', 'unknown')}")
                print("   ✅ RAG Server Health: PASS")
                return True
            else:
                print(f"   ❌ RAG Server Health: FAIL (HTTP {response.status_code})")
                return False
                
    except httpx.ConnectError:
        print(f"   ❌ RAG Server Health: FAIL (not running)")
        print(f"   💡 Start RAG server with: python main.py rag --ingest")
        return False
    except Exception as e:
        print(f"   ❌ RAG Server Health: FAIL ({e})")
        return False


def test_rag_query():
    """Test RAG server query endpoint."""
    print("\n" + "="*60)
    print("🔬 Test 3: RAG Query (End-to-End)")
    print("="*60)
    
    try:
        with httpx.Client(timeout=300.0) as client:
            test_query = "How to handle error spikes in nginx service?"
            
            print(f"   Query: {test_query}")
            print(f"   Sending to {RAG_URL}...")
            print(f"   (This may take 1-2 minutes for DeepSeek reasoning)")
            
            response = client.post(
                f"{RAG_URL}/",
                json={"query": test_query, "n_results": 3}
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result.get("answer", "")
                sources = result.get("sources", [])
                model = result.get("model", "unknown")
                
                print(f"   ✓ Response received!")
                print(f"   Model: {model}")
                print(f"   Sources: {sources}")
                print(f"   Answer ({len(answer)} chars):")
                print(f"   {answer[:300]}{'...' if len(answer) > 300 else ''}")
                
                if answer and len(answer) > 10:
                    print("   ✅ RAG Query: PASS")
                    return True
                else:
                    print("   ❌ RAG Query: FAIL (empty answer)")
                    return False
            else:
                print(f"   ❌ RAG Query: FAIL (HTTP {response.status_code})")
                print(f"   Response: {response.text[:200]}")
                return False
                
    except httpx.ConnectError:
        print(f"   ❌ RAG Query: FAIL (server not running)")
        return False
    except Exception as e:
        print(f"   ❌ RAG Query: FAIL ({e})")
        return False


def main():
    print("="*60)
    print("🧪 OpsPulse AI - Integration Test Suite")
    print("="*60)
    
    results = {
        "DeepSeek LLM": test_deepseek_direct(),
        "RAG Health": test_rag_health(),
        "RAG Query": test_rag_query(),
    }
    
    print("\n" + "="*60)
    print("📊 Test Results Summary")
    print("="*60)
    
    all_passed = True
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"   {test_name}: {status}")
        if not passed:
            all_passed = False
    
    print()
    if all_passed:
        print("🎉 All tests passed! Integration is working.")
    else:
        print("⚠️ Some tests failed. Check the output above for details.")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
