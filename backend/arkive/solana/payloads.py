"""Canonical payload builders for Solana audit anchoring.

Each public function in this module maps a raw ORM object or dict into the
exact deterministic fields that are allowed for a specific audit event type.
The returned dicts are intentionally small: no raw content, no credentials,
and no raw PII. Content-like values are represented by SHA-256 hashes.
"""

from datetime import date, datetime
from hashlib import sha256


def _get(source, field: str, default=None):
    if isinstance(source, dict):
        return source.get(field, default)
    return getattr(source, field, default)


def _iso(value):
    if value is None:
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _hash(value):
    if value is None:
        return None
    return sha256(str(value).encode('utf-8')).hexdigest()


def _list_of_strings(value):
    if value is None:
        return []
    if isinstance(value, dict):
        return sorted(str(key) for key in value.keys())
    if isinstance(value, (list, tuple, set)):
        return sorted(str(item) for item in value)
    return [str(value)]


def payload_http_request(source: dict) -> dict:
    return {
        'user_id': _get(source, 'user_id'),
        'ip_address': _get(source, 'ip_address'),
        'method': _get(source, 'method'),
        'uri': _get(source, 'uri'),
        'status_code': _get(source, 'status_code'),
        'request_body_hash': _hash(_get(source, 'body')),
        'response_status': _get(source, 'response_status'),
    }


def payload_auth_event(source: dict) -> dict:
    return {
        'event': _get(source, 'event'),
        'user_id': _get(source, 'user_id'),
        'email': _hash(_get(source, 'email')),
        'timestamp': _iso(_get(source, 'timestamp')),
    }


def payload_api_key_usage(source: dict) -> dict:
    return {
        'key_id': _get(source, 'key_id'),
        'user_id': _get(source, 'user_id'),
        'used_at': _iso(_get(source, 'used_at')),
        'expires_at': _iso(_get(source, 'expires_at')),
    }


def payload_user_activity(source: dict) -> dict:
    return {
        'user_id': _get(source, 'user_id'),
        'change_type': _get(source, 'change_type'),
        'changed_fields': _list_of_strings(_get(source, 'changed_fields')),
        'changed_at': _iso(_get(source, 'changed_at')),
    }


def payload_chat_event(source: dict) -> dict:
    return {
        'chat_id': _get(source, 'chat_id'),
        'user_id': _get(source, 'user_id'),
        'event_type': _get(source, 'event_type'),
        'title': _get(source, 'title'),
        'share_id': _get(source, 'share_id'),
        'changed_at': _iso(_get(source, 'changed_at')),
    }


def payload_chat_message(source: dict) -> dict:
    return {
        'message_id': _get(source, 'message_id'),
        'chat_id': _get(source, 'chat_id'),
        'user_id': _get(source, 'user_id'),
        'model_id': _get(source, 'model_id'),
        'role': _get(source, 'role'),
        'content_hash': _hash(_get(source, 'content')),
        'token_count': _get(source, 'token_count'),
        'status': _get(source, 'status'),
        'error_code': _get(source, 'error_code'),
    }


def payload_policy_decision(source: dict) -> dict:
    return {
        'decision_id': _get(source, 'decision_id'),
        'user_id': _get(source, 'user_id'),
        'query_hash': _get(source, 'query_hash'),
        'decision': _get(source, 'decision'),
        'sensitivity_level': _get(source, 'sensitivity_level'),
        'routing': _get(source, 'routing'),
        'detected_entity_types': _list_of_strings(_get(source, 'detected_entity_types')),
        'reason': _get(source, 'reason'),
        'created_at': _iso(_get(source, 'created_at')),
    }


def payload_pending_review(source: dict) -> dict:
    return {
        'review_id': _get(source, 'review_id'),
        'user_id': _get(source, 'user_id'),
        'query_hash': _get(source, 'query_hash'),
        'sensitivity_level': _get(source, 'sensitivity_level'),
        'status': _get(source, 'status'),
        'reviewed_by': _get(source, 'reviewed_by'),
        'reviewed_at': _iso(_get(source, 'reviewed_at')),
        'reason': _get(source, 'reason'),
    }


def payload_user_feedback(source: dict) -> dict:
    return {
        'feedback_id': _get(source, 'feedback_id'),
        'user_id': _get(source, 'user_id'),
        'model_id': _get(source, 'model_id'),
        'rating': _get(source, 'rating'),
        'comment_hash': _hash(_get(source, 'comment')),
        'chat_id': _get(source, 'chat_id'),
        'created_at': _iso(_get(source, 'created_at')),
    }


def payload_document_classification(source: dict) -> dict:
    return {
        'file_id': _get(source, 'file_id'),
        'sensitivity_level': _get(source, 'sensitivity_level'),
        'topic_labels': _list_of_strings(_get(source, 'topic_labels')),
        'entity_types_detected': _list_of_strings(_get(source, 'entity_types_detected')),
        'classification_method': _get(source, 'classification_method'),
        'classified_at': _iso(_get(source, 'classified_at')),
    }


def payload_knowledge_base_event(source: dict) -> dict:
    return {
        'kb_id': _get(source, 'kb_id'),
        'user_id': _get(source, 'user_id'),
        'event_type': _get(source, 'event_type'),
        'file_id': _get(source, 'file_id'),
        'changed_at': _iso(_get(source, 'changed_at')),
    }


def payload_file_upload(source: dict) -> dict:
    return {
        'file_id': _get(source, 'file_id'),
        'user_id': _get(source, 'user_id'),
        'filename_hash': _hash(_get(source, 'filename')),
        'file_hash': _get(source, 'file_hash'),
        'content_type': _get(source, 'content_type'),
        'file_size': _get(source, 'file_size'),
        'uploaded_at': _iso(_get(source, 'uploaded_at')),
    }


def payload_channel_event(source: dict) -> dict:
    return {
        'channel_id': _get(source, 'channel_id'),
        'user_id': _get(source, 'user_id'),
        'event_type': _get(source, 'event_type'),
        'changed_at': _iso(_get(source, 'changed_at')),
    }


def payload_channel_membership(source: dict) -> dict:
    return {
        'channel_id': _get(source, 'channel_id'),
        'user_id': _get(source, 'user_id'),
        'event_type': _get(source, 'event_type'),
        'changed_at': _iso(_get(source, 'changed_at')),
    }


def payload_message_event(source: dict) -> dict:
    return {
        'message_id': _get(source, 'message_id'),
        'channel_id': _get(source, 'channel_id'),
        'user_id': _get(source, 'user_id'),
        'content_hash': _hash(_get(source, 'content')),
        'pinned_by': _get(source, 'pinned_by'),
        'reaction_count': _get(source, 'reaction_count'),
        'created_at': _iso(_get(source, 'created_at')),
    }


def payload_oauth_session(source: dict) -> dict:
    return {
        'session_id': _get(source, 'session_id'),
        'user_id': _get(source, 'user_id'),
        'provider': _get(source, 'provider'),
        'created_at': _iso(_get(source, 'created_at')),
        'expires_at': _iso(_get(source, 'expires_at')),
    }


def payload_prompt_history(source: dict) -> dict:
    return {
        'prompt_id': _get(source, 'prompt_id'),
        'version': _get(source, 'version'),
        'user_id': _get(source, 'user_id'),
        'content_hash': _hash(_get(source, 'content')),
        'commit_message': _get(source, 'commit_message'),
        'created_at': _iso(_get(source, 'created_at')),
    }


def payload_access_grant(source: dict) -> dict:
    return {
        'grant_id': _get(source, 'grant_id'),
        'grantor_id': _get(source, 'grantor_id'),
        'grantee_id': _get(source, 'grantee_id'),
        'resource_type': _get(source, 'resource_type'),
        'resource_id': _get(source, 'resource_id'),
        'permission_level': _get(source, 'permission_level'),
        'granted_at': _iso(_get(source, 'granted_at')),
        'expires_at': _iso(_get(source, 'expires_at')),
    }


def payload_analytics_snapshot(source: dict) -> dict:
    return {
        'user_id': _get(source, 'user_id'),
        'model_id': _get(source, 'model_id'),
        'period_start': _iso(_get(source, 'period_start')),
        'period_end': _iso(_get(source, 'period_end')),
        'message_count': _get(source, 'message_count'),
        'total_tokens': _get(source, 'total_tokens'),
    }


def payload_trace_event(source: dict) -> dict:
    return {
        'trace_id': _get(source, 'trace_id'),
        'span_id': _get(source, 'span_id'),
        'service_name': _get(source, 'service_name'),
        'operation_name': _get(source, 'operation_name'),
        'status': _get(source, 'status'),
        'duration_ms': _get(source, 'duration_ms'),
        'started_at': _iso(_get(source, 'started_at')),
    }
