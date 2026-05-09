"""Confidence scoring utility — Calculate combined confidence metrics."""

import logging
from typing import Any, Dict, List, Optional

from arkive.models.confidence_scores import ConfidenceScores
from arkive.models.response_audits import ResponseAudits

log = logging.getLogger(__name__)


async def calculate_confidence_score(
    audit_log_id: str,
    retrieved_sources: List[Dict[str, Any]],
    fact_check_results: List[Dict[str, Any]],
    classification_score: float,
) -> Dict[str, Any]:
    """
    Calculate combined confidence score from three signals.

    This is the main scoring function used in the chat flow.
    It combines:
    - Source Quality (40% weight) — How good are the retrieved documents?
    - Fact-Check (40% weight) — How well do facts match the sources?
    - Classification (20% weight) — How safe/appropriate is the query?

    Formula: final = 0.4*sq + 0.4*fc + 0.2*cs

    Args:
        audit_log_id: ID of the response audit log
        retrieved_sources: List of dicts like:
            [{'source_id': '...', 'quality': 0.85, 'relevance': 0.9}, ...]
        fact_check_results: List of dicts like:
            [{'verdict': 'supported', 'confidence': 0.95}, ...]
        classification_score: Policy/safety score (0-1) from policy engine

    Returns:
        Dict with:
        {
            'final_confidence': float (0-1),
            'source_quality_score': float,
            'fact_check_score': float,
            'classification_score': float,
            'score_record_id': str (UUID of saved score),
            'breakdown': {...},
            'interpretation': str,
        }
    """

    # ──────────────────────────────────────────────────────────────
    # SIGNAL 1: Source Quality Score
    # ──────────────────────────────────────────────────────────────
    # Average the quality scores from retrieved documents
    # If no sources, use 0 (conservative)

    if not retrieved_sources:
        source_quality_score = 0.0
        log.debug('[confidence] no sources retrieved, sq=0.0')
    else:
        quality_scores = []
        for source in retrieved_sources:
            quality = source.get('quality', source.get('relevance', 0.5))
            quality_scores.append(max(0, min(1, quality)))

        source_quality_score = sum(quality_scores) / len(quality_scores)
        log.debug(
            f'[confidence] {len(retrieved_sources)} sources, '
            f'avg quality={source_quality_score:.2f}'
        )

    # ──────────────────────────────────────────────────────────────
    # SIGNAL 2: Fact-Check Score
    # ──────────────────────────────────────────────────────────────
    # Aggregate fact-check verdicts weighted by LLM confidence
    #
    # Verdict weight mapping:
    #   'supported'               → 1.0  (facts fully match sources)
    #   'partially_supported'     → 0.6  (some facts match, some uncertain)
    #   'not_verified'            → 0.3  (facts not found in sources)
    #   'contradicted'            → 0.0  (facts contradict sources)
    #
    # Each verdict is weighted by the LLM's confidence in that verdict

    if not fact_check_results:
        # No fact-checking happened yet (e.g., dev team not done yet)
        # Use neutral default
        fact_check_score = 0.5
        log.debug('[confidence] no fact-check results, using neutral 0.5')
    else:
        verdict_weights = {
            'supported': 1.0,
            'partially_supported': 0.6,
            'not_verified': 0.3,
            'contradicted': 0.0,
        }

        weighted_sum = 0.0
        confidence_sum = 0.0

        for result in fact_check_results:
            verdict = result.get('verdict', 'not_verified')
            conf = max(0, min(1, result.get('confidence', 0.5)))

            weight = verdict_weights.get(verdict, 0.3)  # Default to 'not_verified'
            weighted_sum += weight * conf
            confidence_sum += conf

        fact_check_score = (
            weighted_sum / confidence_sum if confidence_sum > 0 else 0.5
        )
        log.debug(
            f'[confidence] {len(fact_check_results)} facts checked, '
            f'fc_score={fact_check_score:.2f}'
        )

    # ──────────────────────────────────────────────────────────────
    # SIGNAL 3: Classification Score
    # ──────────────────────────────────────────────────────────────
    # Already provided by policy engine (query sensitivity / safety)
    # Just clamp to [0, 1]

    classification_score = max(0, min(1, classification_score))

    # ──────────────────────────────────────────────────────────────
    # FINAL COMBINATION
    # ──────────────────────────────────────────────────────────────
    # Weighted average: 40% source + 40% fact-check + 20% policy
    # Each component is already in [0, 1]

    WEIGHTS = {
        'source_quality': 0.4,
        'fact_check': 0.4,
        'classification': 0.2,
    }

    final_confidence = (
        WEIGHTS['source_quality'] * source_quality_score
        + WEIGHTS['fact_check'] * fact_check_score
        + WEIGHTS['classification'] * classification_score
    )
    final_confidence = max(0, min(1, final_confidence))

    # ──────────────────────────────────────────────────────────────
    # Persist to database
    # ──────────────────────────────────────────────────────────────

    score_record = ConfidenceScores.insert_score(
        response_audit_log_id=audit_log_id,
        source_quality_score=source_quality_score,
        fact_check_score=fact_check_score,
        classification_score=classification_score,
        formula="0.4*sq + 0.4*fc + 0.2*cs",
    )

    score_record_id = str(score_record.id) if score_record else None

    log.info(
        f'[confidence] audit_log={audit_log_id} '
        f'sq={source_quality_score:.2f} '
        f'fc={fact_check_score:.2f} '
        f'cs={classification_score:.2f} '
        f'→ final={final_confidence:.2f}'
    )

    # ──────────────────────────────────────────────────────────────
    # Format response
    # ──────────────────────────────────────────────────────────────

    return {
        'final_confidence': final_confidence,
        'source_quality_score': source_quality_score,
        'fact_check_score': fact_check_score,
        'classification_score': classification_score,
        'score_record_id': score_record_id,
        'breakdown': {
            'source_quality': {
                'score': source_quality_score,
                'weight': WEIGHTS['source_quality'],
            },
            'fact_check': {
                'score': fact_check_score,
                'weight': WEIGHTS['fact_check'],
            },
            'classification': {
                'score': classification_score,
                'weight': WEIGHTS['classification'],
            },
        },
        'interpretation': _interpret_confidence(final_confidence),
    }


def _interpret_confidence(score: float) -> str:
    """
    Human-readable interpretation of confidence score.

    Returns a one-sentence explanation suitable for displaying to users.
    """
    if score >= 0.85:
        return 'High confidence — answer is well-supported by sources'
    elif score >= 0.65:
        return 'Moderate confidence — answer has reasonable support'
    elif score >= 0.45:
        return 'Low confidence — answer has limited support'
    else:
        return 'Very low confidence — answer may be unreliable'
