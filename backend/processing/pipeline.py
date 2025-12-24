"""
Processing pipeline orchestrator.
"""
from typing import Dict, Any, Optional
from datetime import datetime

from ..database import DatabaseManager
from .llm_processor import LLMProcessor
from .lean_converter import LeanConverter


class ProcessingPipeline:
    """
    Orchestrates the complete processing pipeline for questions.

    Pipeline stages:
    1. Image OCR (GLM-4V)
    2. LLM Preprocessing (GLM-4)
    3. Deduplication (interface only, not implemented)
    4. Lean Conversion (Kimina-Autoformalizer-7B)
    """

    def __init__(
        self,
        db_manager: DatabaseManager,
        zhipu_api_key: str,
        vllm_base_url: str = "http://localhost:8000/v1",
        vllm_model_path: str = "/root/Kimina-Autoformalizer-7B"
    ):
        """
        Initialize processing pipeline.

        Args:
            db_manager: Database manager instance
            zhipu_api_key: Zhipu API key for GLM-4V/4
            vllm_base_url: VLLM server URL
            vllm_model_path: Model path
        """
        self.db = db_manager
        self.llm_processor = LLMProcessor(db_manager, zhipu_api_key)
        self.lean_converter = LeanConverter(db_manager, vllm_base_url, vllm_model_path)

    def process_question(
        self,
        question_internal_id: int,
        skip_ocr: bool = False,
        skip_preprocessing: bool = False,
        skip_lean: bool = False
    ) -> Dict[str, Any]:
        """
        Process a question through the pipeline.

        Args:
            question_internal_id: Internal database question ID
            skip_ocr: Skip OCR stage
            skip_preprocessing: Skip preprocessing stage
            skip_lean: Skip Lean conversion stage

        Returns:
            Processing result with stage information
        """
        question = self.db.get_question(question_internal_id)
        if not question:
            raise ValueError(f"Question {question_internal_id} not found")

        result = {
            'question_id': question_internal_id,
            'stages_completed': [],
            'stages_skipped': [],
            'final_status': None
        }

        current_status = question.get('processing_status', {}).get('status', 'raw')

        # Stage 1: LLM Preprocessing (includes OCR)
        if not skip_preprocessing and current_status in ['raw']:
            try:
                self.llm_processor.process_question(question_internal_id)
                result['stages_completed'].append('preprocessing')
                current_status = 'preprocessed'
            except Exception as e:
                result['error'] = str(e)
                result['final_status'] = 'failed'
                return result
        else:
            result['stages_skipped'].append('preprocessing')

        # Stage 2: Deduplication (interface only)
        # Not implemented yet
        result['stages_skipped'].append('deduplication')

        # Stage 3: Lean Conversion
        if not skip_lean and current_status in ['preprocessed']:
            try:
                self.lean_converter.convert_question(question_internal_id)
                result['stages_completed'].append('lean_conversion')
                result['final_status'] = 'lean_converted'
            except Exception as e:
                result['error'] = str(e)
                result['final_status'] = 'failed'
                return result
        else:
            result['stages_skipped'].append('lean_conversion')

        if not result['final_status']:
            result['final_status'] = current_status

        return result

    def process_batch(
        self,
        question_ids: list,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Process a batch of questions.

        Args:
            question_ids: List of internal question IDs
            **kwargs: Arguments to pass to process_question

        Returns:
            Batch processing result
        """
        results = {
            'total': len(question_ids),
            'successful': 0,
            'failed': 0,
            'details': []
        }

        for qid in question_ids:
            try:
                result = self.process_question(qid, **kwargs)
                if result.get('final_status') == 'lean_converted':
                    results['successful'] += 1
                else:
                    results['failed'] += 1
                results['details'].append({
                    'question_id': qid,
                    'result': result
                })
            except Exception as e:
                results['failed'] += 1
                results['details'].append({
                    'question_id': qid,
                    'error': str(e)
                })

        return results

    def get_pending_count(self, status: str = 'raw') -> int:
        """Get count of questions pending processing."""
        questions = self.db.get_questions_by_status(status, limit=1000000)
        return len(questions)
