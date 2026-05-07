"""Response composer utility — Assemble final response with all components."""

import logging
from typing import Any, Dict, List, Optional

from arkive.models.response_audits import ResponseAudits, AuditStage

log = logging.getLogger(__name__)


class ResponseComposer:
    """
    Assembles the final response that gets sent to the user.

    Takes component parts:
    - Answer text
    - Confidence scores + breakdown
    - Source citations
    - Redaction flags
    - Audit trail ID

    Returns a structured response with all pieces together.
    """

    @staticmethod
    async def compose(
        message_id: str,
        user_id: str,
        answer_text: str,
        confidence_score: float,
        confidence_breakdown: Dict[str, Any],
        citations: List[Dict[str, Any]],
        redacted_entities: Optional[List[Dict[str, Any]]] = None,
        response_audit_log_id: Optional[str] = None,
        policy_decision_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        Assemble the final response for the client.

        Args:
            message_id: ID of the chat message
            user_id: ID of the user
            answer_text: The actual answer from the LLM
            confidence_score: Final confidence (0-1)
            confidence_breakdown: Dict with breakdown by source/fact/policy
            citations: List of retrieved sources used
            redacted_entities: List of PII types that were redacted (optional)
            response_audit_log_id: ID of the response audit log
            policy_decision_id: ID of the policy decision (optional)

        Returns:
            Dict with structured response, or None if composition failed

        Response structure:
        {
            'response': {
                'answer': str,
                'confidence': {
                    'score': float,
                    'breakdown': {...},
                    'interpretation': str,
                },
                'citations': [...],
                'redaction_notice': {...} or null,
            },
            'audit': {
                'response_audit_log_id': str,
                'policy_decision_id': str or null,
            }
        }
        """

        try:
            # ──────────────────────────────────────────────────────────────
            # Stage 1: Validate inputs
            # ──────────────────────────────────────────────────────────────

            if not answer_text or not str(answer_text).strip():
                log.error(
                    f'[compose] message_id={message_id} '
                    f'answer_text is empty'
                )
                return None

            if not (0 <= confidence_score <= 1):
                log.error(
                    f'[compose] message_id={message_id} '
                    f'confidence_score out of range: {confidence_score}'
                )
                return None

            # ──────────────────────────────────────────────────────────────
            # Stage 2: Create redaction notice (if applicable)
            # ──────────────────────────────────────────────────────────────
            # If PII was detected and redacted, show a notice to the user

            redaction_notice = None
            if redacted_entities and len(redacted_entities) > 0:
                entity_types = list(
                    set(e.get('type', 'UNKNOWN') for e in redacted_entities)
                )
                total_count = sum(
                    e.get('count', 1) for e in redacted_entities
                )

                redaction_notice = {
                    'was_redacted': True,
                    'entity_types': entity_types,
                    'entity_count': total_count,
                    'message': (
                        f'This response was redacted to remove {total_count} '
                        f'sensitive information item(s) ({", ".join(entity_types)}). '
                        f'Ask an admin if you need clarification.'
                    ),
                }

                log.info(
                    f'[compose] message_id={message_id} '
                    f'redacted {total_count} entities: {entity_types}'
                )

            # ──────────────────────────────────────────────────────────────
            # Stage 3: Format citations
            # ──────────────────────────────────────────────────────────────
            # Convert citations to display-friendly format

            formatted_citations = []
            for i, citation in enumerate(citations, 1):
                source_text = citation.get('source_text', '')
                # Truncate to first 500 chars to keep response size reasonable
                snippet = source_text[:500] if source_text else '[No preview]'

                formatted_citations.append({
                    'index': i,
                    'source_id': citation.get('source_id', f'source_{i}'),
                    'text_snippet': snippet,
                    'relevance': citation.get('relevance_score', 0.5),
                    'title': citation.get('title', 'Source'),
                })

            log.info(
                f'[compose] message_id={message_id} '
                f'formatted {len(formatted_citations)} citations'
            )

            # ──────────────────────────────────────────────────────────────
            # Stage 4: Assemble response object
            # ──────────────────────────────────────────────────────────────

            final_response = {
                'response': {
                    'answer': str(answer_text).strip(),
                    'confidence': {
                        'score': float(confidence_score),
                        'breakdown': confidence_breakdown,
                        'interpretation': confidence_breakdown.get(
                            'interpretation',
                            'Confidence calculation complete'
                        ),
                    },
                    'citations': formatted_citations,
                    'redaction_notice': redaction_notice,
                },
                'audit': {
                    'response_audit_log_id': response_audit_log_id,
                    'policy_decision_id': policy_decision_id,
                },
            }

            # ──────────────────────────────────────────────────────────────
            # Stage 5: Log composition to audit trail
            # ──────────────────────────────────────────────────────────────

            try:
                ResponseAudits.insert_stage_log(
                    user_id=user_id,
                    message_id=message_id,
                    stage=AuditStage.RESPONSE_COMPOSITION,
                    status='success',
                    stage_input={
                        'answer_length': len(answer_text),
                        'confidence_score': confidence_score,
                    },
                    stage_output={
                        'answer_length': len(answer_text),
                        'citation_count': len(formatted_citations),
                        'redacted': redaction_notice is not None,
                    },
                    duration_ms=0,  # Set by caller if timing needed
                )
            except Exception as audit_err:
                # Audit failure should not block response composition
                log.warning(
                    f'[compose] failed to log composition stage: {audit_err}'
                )

            log.info(
                f'[compose] message_id={message_id} user_id={user_id} '
                f'confidence={confidence_score:.2f} '
                f'citations={len(formatted_citations)} '
                f'redacted={redaction_notice is not None}'
            )

            return final_response

        except Exception as e:
            log.exception(f'[compose] unexpected error: {e}')
            return None


def interpret_confidence(score: float) -> str:
    """
    Get human-readable interpretation of confidence score.

    Used by the UI to show what the score means to end users.
    """
    if score >= 0.85:
        return '✅ High confidence — well-supported by sources'
    elif score >= 0.65:
        return '⚠️ Moderate confidence — reasonably supported'
    elif score >= 0.45:
        return '⚠️ Low confidence — limited support'
    else:
        return '❌ Very low confidence — may be unreliable'
