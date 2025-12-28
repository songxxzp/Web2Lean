#!/usr/bin/env python3
"""
Interactive Lean Converter Test Tool

Usage:
    python test_lean_converter.py
"""
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from backend.processing.lean_converter import LeanConverter
from backend.config import get_settings


def test_question(converter: LeanConverter):
    """Test question conversion."""
    print("\n" + "="*60)
    print("Test Question Conversion")
    print("="*60)

    title = input("\nEnter question title: ").strip()
    if not title:
        print("Error: Title cannot be empty")
        return

    body = input("\nEnter question body (press Enter twice to finish):\n").strip()
    if not body:
        print("Error: Body cannot be empty")
        return

    print(f"\n{'='*60}")
    print("Converting...")
    print("="*60)

    try:
        result = converter._convert_question_to_lean(title, body)

        print("\n" + "="*60)
        print("Result:")
        print("="*60)
        print(result)
        print("="*60)
    except Exception as e:
        print(f"\nError during conversion: {e}")


def test_answer(converter: LeanConverter):
    """Test answer conversion."""
    print("\n" + "="*60)
    print("Test Answer Conversion")
    print("="*60)

    title = input("\nEnter question title: ").strip()
    if not title:
        print("Error: Title cannot be empty")
        return

    body = input("\nEnter question body (press Enter twice to finish):\n").strip()
    if not body:
        print("Error: Body cannot be empty")
        return

    answer = input("\nEnter answer/solution (press Enter twice to finish):\n").strip()
    if not answer:
        print("Error: Answer cannot be empty")
        return

    print(f"\n{'='*60}")
    print("Converting...")
    print("="*60)

    try:
        result = converter._convert_answer_to_lean(title, body, answer)

        print("\n" + "="*60)
        print("Result:")
        print("="*60)
        print(result)
        print("="*60)
    except Exception as e:
        print(f"\nError during conversion: {e}")


def main():
    """Main entry point."""
    print("="*60)
    print("Lean Converter Interactive Test")
    print("="*60)

    # Load settings
    settings = get_settings()

    print(f"\nConfiguration:")
    print(f"  VLLM URL: {settings.vllm_base_url}")
    print(f"  Model: {settings.vllm_model_path}")

    # Create converter
    try:
        converter = LeanConverter(
            db_manager=None,  # Not needed for conversion tests
            vllm_base_url=settings.vllm_base_url,
            model_path=settings.vllm_model_path
        )
        print("\n✓ Converter initialized successfully")
    except Exception as e:
        print(f"\n✗ Failed to initialize converter: {e}")
        print("\nPlease ensure VLLM server is running at the configured URL.")
        sys.exit(1)

    # Main loop
    while True:
        print("\n" + "="*60)
        print("Select test type:")
        print("  1. Test Question Conversion (_convert_question_to_lean)")
        print("  2. Test Answer Conversion (_convert_answer_to_lean)")
        print("  3. Exit")
        print("="*60)

        choice = input("\nEnter your choice (1-3): ").strip()

        if choice == '1':
            test_question(converter)
        elif choice == '2':
            test_answer(converter)
        elif choice == '3':
            print("\nGoodbye!")
            break
        else:
            print("\nInvalid choice. Please enter 1, 2, or 3.")


if __name__ == '__main__':
    main()
