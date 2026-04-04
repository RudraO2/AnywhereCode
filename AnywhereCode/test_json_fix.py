#!/usr/bin/env python3
"""
Test script to verify JSON parsing fix for Gemini API.

Tests the robust JSON extraction with various response formats.
"""

import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from anyplace.core.llm_provider import LLMProvider
from anyplace.core.mock_llm import MockLLMProvider


def test_extract_json():
    """Test JSON extraction from various formats."""
    provider = LLMProvider.__new__(LLMProvider)

    test_cases = [
        # Plain JSON
        ('{"key": "value"}', {"key": "value"}),

        # JSON with markdown fences
        ('```json\n{"key": "value"}\n```', {"key": "value"}),

        # JSON with surrounding text
        ('Here is the JSON:\n{"key": "value"}\nThat was it.', {"key": "value"}),

        # JSON in code block
        ('```\n{"key": "value"}\n```', {"key": "value"}),

        # JSON with extra spaces
        ('  {\n  "key": "value"\n}  ', {"key": "value"}),

        # Complex nested JSON
        ('```json\n{\n  "project": "test",\n  "files": [{"path": "main.py"}]\n}\n```',
         {"project": "test", "files": [{"path": "main.py"}]}),
    ]

    print("Testing JSON extraction...")
    passed = 0
    failed = 0

    for i, (input_str, expected) in enumerate(test_cases, 1):
        try:
            result = provider._extract_json_from_response(input_str)
            if result == expected:
                print(f"✅ Test {i} PASS")
                passed += 1
            else:
                print(f"❌ Test {i} FAIL")
                print(f"   Expected: {expected}")
                print(f"   Got: {result}")
                failed += 1
        except Exception as e:
            print(f"❌ Test {i} ERROR: {e}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed")
    return failed == 0


def test_mock_json_generation():
    """Test JSON generation with mock LLM."""
    print("\n" + "="*60)
    print("Testing JSON generation with MockLLMProvider...")
    print("="*60)

    mock = MockLLMProvider()

    # This simulates what plan_generator.py does
    prompt = "Generate a project plan"
    response = mock.generate_text(prompt, json_mode=True)

    print(f"\nMock response type: {type(response)}")
    print(f"First 200 chars: {response[:200]}")

    try:
        # Parse it
        data = json.loads(response)
        print("✅ Mock JSON parsed successfully")
        print(f"   Project name: {data.get('project_name')}")
        return True
    except Exception as e:
        print(f"❌ Failed to parse mock JSON: {e}")
        return False


def test_plan_generation():
    """Test actual plan generation with mock LLM."""
    print("\n" + "="*60)
    print("Testing plan generation with MockLLMProvider...")
    print("="*60)

    from anyplace.core.plan_generator import PlanGenerator
    from anyplace.config.api_manager import APIManager

    try:
        # Use mock LLM
        api_manager = APIManager()
        api_manager.config = {"mock": {"api_key": "mock", "model": "mock"}}
        api_manager.active_provider = "mock"
        api_manager.llm_provider = MockLLMProvider()

        llm_provider = LLMProvider.__new__(LLMProvider)
        llm_provider.api_manager = api_manager
        llm_provider.provider = "mock"
        llm_provider.llm_provider = MockLLMProvider()

        # Override the provider to use mock
        llm_provider._dispatch = lambda *args, **kwargs: MockLLMProvider().generate_text(
            "Generate a plan", json_mode=True
        )

        generator = PlanGenerator(llm_provider=llm_provider)

        # Try to generate a plan
        plan = generator.generate_plan(
            template_name="web-react-vite",
            project_name="test-project",
            description="A test project"
        )

        print("✅ Plan generated successfully")
        print(f"   Project: {plan.project_name}")
        print(f"   Template: {plan.template}")
        print(f"   Files: {len(plan.files)}")
        return True

    except Exception as e:
        print(f"❌ Plan generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    all_passed = True

    # Test 1: JSON extraction
    if not test_extract_json():
        all_passed = False

    # Test 2: Mock JSON generation
    if not test_mock_json_generation():
        all_passed = False

    # Test 3: Plan generation
    if not test_plan_generation():
        all_passed = False

    print("\n" + "="*60)
    if all_passed:
        print("✅ All tests PASSED")
        sys.exit(0)
    else:
        print("❌ Some tests FAILED")
        sys.exit(1)
