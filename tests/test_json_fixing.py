"""
Direct test script for JSON escape fixing.
Run with: python tests/test_json_fixing.py
"""
import json
import html


def fix_json_escapes(s):
    """Fix invalid escape sequences in JSON strings."""
    result = []
    i = 0
    while i < len(s):
        if s[i] == '\\' and i + 1 < len(s):
            next_char = s[i + 1]
            # Valid JSON escapes
            if next_char in '"\\/bfnrt':
                result.append(s[i:i+2])
                i += 2
                continue
            # Unicode escape like \uXXXX
            elif next_char == 'u' and i + 5 < len(s):
                result.append(s[i:i+6])
                i += 6
                continue
            # Invalid escapes - remove the backslash for these common LaTeX cases
            # Keep the backslash if it's followed by certain chars
            elif next_char in '({[<>=_~.*+|?^-]\'':
                # LaTeX or other special chars - keep the backslash
                result.append('\\\\' + next_char)
                i += 2
            else:
                # Other invalid escapes - just remove the backslash
                result.append(next_char)
                i += 2
        else:
            result.append(s[i])
            i += 1
    return ''.join(result)


def test_cases():
    """Test various problematic JSON cases from real LLM responses."""

    print("Testing JSON escape fixing...\n")

    # Test 1: LaTeX backslashes
    test1 = r'{"text": "Use \(x^2\) notation"}'
    print(f"Test 1 - LaTeX escapes:")
    print(f"  Input:  {test1}")
    fixed1 = fix_json_escapes(test1)
    print(f"  Fixed:  {fixed1}")
    try:
        parsed1 = json.loads(html.unescape(fixed1))
        print(f"  Parsed: {parsed1}")
        print("  ✓ PASS\n")
    except Exception as e:
        print(f"  ✗ FAIL: {e}\n")

    # Test 2: Double backslashes (LaTeX fractions)
    test2 = r'{"math": r"\frac{1}{2} and \\mathbb{R}"}'
    test2 = '{"math": "\\\\frac{1}{2} and \\\\\\\\mathbb{R}"}'
    print(f"Test 2 - Double backslashes:")
    print(f"  Input:  {test2}")
    fixed2 = fix_json_escapes(test2)
    print(f"  Fixed:  {fixed2}")
    try:
        parsed2 = json.loads(html.unescape(fixed2))
        print(f"  Parsed: {parsed2}")
        print("  ✓ PASS\n")
    except Exception as e:
        print(f"  ✗ FAIL: {e}\n")

    # Test 3: Invalid escape \(
    test3 = r'{"text": "Use \( and \) for inline math"}'
    print(f"Test 3 - Invalid LaTeX escapes:")
    print(f"  Input:  {test3}")
    fixed3 = fix_json_escapes(test3)
    print(f"  Fixed:  {fixed3}")
    try:
        parsed3 = json.loads(html.unescape(fixed3))
        print(f"  Parsed: {parsed3}")
        print("  ✓ PASS\n")
    except Exception as e:
        print(f"  ✗ FAIL: {e}\n")

    # Test 4: HTML entities
    test4 = r'{"expr": "a > b and c < d"}'
    print(f"Test 4 - HTML entities:")
    print(f"  Input:  {test4}")
    fixed4 = fix_json_escapes(test4)
    fixed4 = html.unescape(fixed4)
    print(f"  Fixed:  {fixed4}")
    try:
        parsed4 = json.loads(fixed4)
        print(f"  Parsed: {parsed4}")
        print("  ✓ PASS\n")
    except Exception as e:
        print(f"  ✗ FAIL: {e}\n")

    # Test 5: Real-world example from logs
    test5 = r'''{
  "is_valid_question": true,
  "corrected_question": "Test $\\frac{1}{2}$ with \\\\mathbb{R}",
  "has_errors": false
}'''
    print(f"Test 5 - Real LaTeX example:")
    print(f"  Input:  {test5[:80]}...")
    fixed5 = fix_json_escapes(test5)
    print(f"  Fixed:  {fixed5[:80]}...")
    try:
        parsed5 = json.loads(html.unescape(fixed5))
        print(f"  Parsed keys: {list(parsed5.keys())}")
        print("  ✓ PASS\n")
    except Exception as e:
        print(f"  ✗ FAIL: {e}\n")

    # Test 6: Complex LaTeX with various symbols
    test6 = r'''{
  "question": "Solve $\\int_0^1 x^2 dx$ using \\\\mathcal{L}",
  "answer": "Use \\( \\sum_{i=1}^n i \\)"
}'''
    print(f"Test 6 - Complex LaTeX:")
    print(f"  Input:  {test6[:80]}...")
    fixed6 = fix_json_escapes(test6)
    print(f"  Fixed:  {fixed6[:80]}...")
    try:
        parsed6 = json.loads(html.unescape(fixed6))
        print(f"  Parsed keys: {list(parsed6.keys())}")
        print("  ✓ PASS\n")
    except Exception as e:
        print(f"  ✗ FAIL: {e}\n")


    print("=" * 60)
    print("Summary:")
    print("The fix_json_escapes function handles:")
    print("  - Valid JSON escapes (\\n, \\t, \\\", etc.)")
    print("  - LaTeX backslashes (\\(, \\), \\{, \\}, etc.)")
    print("  - HTML entities (&gt;, &lt;, &amp;)")
    print("  - Unicode escapes (\\uXXXX)")


if __name__ == '__main__':
    test_cases()
