"""
LLM Prompt Templates for Web2Lean preprocessing.

This module contains all prompt templates used for LLM-based preprocessing
of mathematical questions and answers.
"""


# Prompt for processing a question without any answer
QUESTION_ONLY_PROMPT = """
You are an expert mathematical reviewer and editor.

Your task is to analyze a mathematical QUESTION extracted from a Q&A website.
You must determine whether the question is mathematically meaningful and correct,
and whether it is worth formalizing into a precise, formal mathematical problem.

--- QUESTION ---
{question}

You must follow this decision process strictly:

1. Determine whether the question is mathematically meaningful.
   - If the question is ill-posed, self-contradictory, meaningless, or nonsensical:
     - Set "is_valid_question" = false
     - Set "worth_formalizing" = false
     - Do NOT attempt to repair the question.
     - Explain the reasons in "errors" and "correction_notes".

2. If the question is meaningful, check for mathematical or factual errors.
   - Errors include (but are not limited to):
     - False mathematical statements
     - Incorrect definitions or misuse of terminology
     - Internal logical contradictions
   - If errors exist:
     - Set "has_errors" = true
     - List all concrete errors in "errors"
     - If the question can be reasonably repaired into a correct and standard form,
       rewrite it in "corrected_question".
     - Otherwise, set "worth_formalizing" = false.

3. If the question is mathematically correct but informal, vague, or colloquial:
   - Rewrite it into a precise, formal, and standard mathematical problem
     in "corrected_question", without changing its meaning.

4. If the question is already correct and formal:
   - Copy it verbatim into "corrected_question".

5. Value assessment.
   - Assess the value of formalizing this question:
     - "low": trivial facts or routine exercises
     - "medium": standard problems suitable for teaching or reference
     - "high": nontrivial, conceptually important, or insightful questions
   - If the question lacks mathematical or educational value:
     - Set "worth_formalizing" = false.

Output requirements (STRICT):
- Output ONLY raw JSON.
- Do NOT include any text outside JSON.
- Use the following exact JSON schema:

{{
  "is_valid_question": boolean,
  "has_errors": boolean,
  "errors": [string],
  "corrected_question": string,
  "correction_notes": string,
  "worth_formalizing": boolean,
  "formalization_value": "low" | "medium" | "high"
}}
""".strip()


# Prompt for processing a question with a single answer
QUESTION_WITH_ANSWER_PROMPT = """
You are an expert mathematical reviewer and editor.

Your task is to analyze a QUESTION–ANSWER pair extracted from a math Q&A website.
You must judge the correctness, consistency, and value of both the question and the answer,
and then formalize them if appropriate.

--- INPUT ---
Q: {question}
A: {answer}

You must follow this decision process strictly:

1. Evaluate the QUESTION.
   - If the question is ill-posed, meaningless, or self-contradictory:
     - Set "is_valid_question" = false
     - Set "worth_formalizing" = false
     - Do NOT attempt to repair it.
     - Record reasons in "errors" and "correction_notes".

2. Evaluate the ANSWER.
   - Determine whether the answer addresses the question.
   - Check whether it is mathematically correct and logically sound.
   - If the question is valid but the answer is incorrect, incomplete, or irrelevant:
     - Set "is_valid_answer" = false
     - Record all issues in "errors".

3. Error handling.
   - Set "has_errors" = true if either the question or the answer contains errors.
   - If errors exist and cannot be reasonably repaired:
     - Set "worth_formalizing" = false.

4. Formalization.
   - Rewrite the question and answer into precise, formal, and standard mathematical language
     in "corrected_question" and "corrected_answer".
   - Preserve the original mathematical meaning.
   - If already formal and correct, copy verbatim.

5. Value assessment.
   - Assess the value of formalizing this question–answer pair:
     - "low": trivial or routine
     - "medium": standard educational value
     - "high": nontrivial or insightful
   - If the pair lacks value:
     - Set "worth_formalizing" = false.

Output requirements (STRICT):
- Output ONLY raw JSON.
- Do NOT include any text outside JSON.
- Use the following exact JSON schema:

{{
  "is_valid_question": boolean,
  "is_valid_answer": boolean,
  "has_errors": boolean,
  "errors": [string],
  "corrected_question": string,
  "corrected_answer": string,
  "correction_notes": string,
  "worth_formalizing": boolean,
  "formalization_value": "low" | "medium" | "high"
}}
""".strip()


# Prompt for processing a question with multiple answers
QUESTION_WITH_MULTIPLE_ANSWERS_PROMPT = """
You are an expert mathematical reviewer and editor.

Your task is to analyze a mathematical QUESTION together with MULTIPLE candidate ANSWERS
extracted from a Q&A website. You must determine whether the question is valid,
whether at least one answer is correct, and then produce a single correct, complete,
and formalized answer.

--- QUESTION ---
{question}

--- CANDIDATE ANSWERS ---
{answers_text}

You must follow this decision process strictly:

1. Evaluate the QUESTION.
   - If the question is ill-posed, meaningless, or self-contradictory:
     - Set "is_valid_question" = false
     - Set "worth_formalizing" = false
     - Do NOT attempt to repair it.
     - Record reasons in "errors" and "correction_notes".

2. Evaluate the ANSWERS collectively.
   - Determine whether at least one candidate answer is mathematically correct
     and addresses the question.
   - Answers may be correct, partially correct, incomplete, or incorrect.
   - You may select the best answer or synthesize a correct answer from multiple answers,
     but you MUST NOT invent new mathematical content.

3. Validity and error handling.
   - Set "is_valid_answer" = true if a correct answer exists or can be synthesized.
   - Set "has_errors" = true if any errors appear in the question or candidate answers.
   - If no correct answer can be obtained:
     - Set "is_valid_answer" = false
     - Set "worth_formalizing" = false.

4. Formalization.
   - Rewrite the question into a precise, formal mathematical problem.
   - Produce a single correct, complete, and formal mathematical answer in
     "corrected_answer", based on the best candidate answer(s).

5. Value assessment.
   - Assess the value of this question–answer pair:
     - "low": trivial
     - "medium": standard educational value
     - "high": nontrivial or insightful
   - If it lacks value:
     - Set "worth_formalizing" = false.

6. Documentation.
   - In "correction_notes", briefly explain which candidate answer(s) were relied upon,
     whether accepted or high-score answers were correct, and what corrections were made.

Output requirements (STRICT):
- Output ONLY raw JSON.
- Do NOT include any text outside JSON.
- Use the following exact JSON schema:

{{
  "is_valid_question": boolean,
  "is_valid_answer": boolean,
  "has_errors": boolean,
  "errors": [string],
  "corrected_question": string,
  "corrected_answer": string,
  "correction_notes": string,
  "worth_formalizing": boolean,
  "formalization_value": "low" | "medium" | "high"
}}
""".strip()


def format_answers_text(answers: list) -> str:
    """
    Format answers list into text for the multiple answers prompt.

    Args:
        answers: List of answer dicts with 'body', 'is_accepted', 'score' keys

    Returns:
        Formatted answers text
    """
    answers_text = ""
    for i, ans in enumerate(answers):
        accepted_mark = " ✓ ACCEPTED" if ans.get('is_accepted') else ""
        score_info = f" (score: {ans.get('score', 0)})" if 'score' in ans else ""
        answers_text += f"\n--- Answer {i+1}{accepted_mark}{score_info} ---\n{ans.get('body', '')}\n"
    return answers_text
