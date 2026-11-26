"""Conservative wire-format repair, not semantic replanning."""
from copy import deepcopy
import re

from cityg.planning.baseline import ROOM_FUNCTIONS


def normalize_program(data):
    """Remove Markdown quoting only from known room-function enum values.

    Unknown terms, function choices, counts and identifiers are never guessed.
    The original response and each change remain available in the agent trace.
    """
    result = deepcopy(data)
    known = {v for values in ROOM_FUNCTIONS.values() for v in values}
    changes = []

    def visit(value, path):
        if isinstance(value, dict):
            for key, child in value.items():
                if key == 'room_function_cycle' and isinstance(child, list):
                    for i, item in enumerate(child):
                        if not isinstance(item, str) or item in known:
                            continue
                        candidate = re.sub(r'^>\s*', '', item.strip()).strip('`').strip()
                        if candidate in known:
                            child[i] = candidate
                            changes.append({'path': f'{path}/{key}/{i}', 'before': item,
                                            'after': candidate, 'reason': 'enum_markdown_wrapper'})
                else:
                    visit(child, f'{path}/{key}')
        elif isinstance(value, list):
            for i, child in enumerate(value):
                visit(child, f'{path}/{i}')
    visit(result, '')
    return result, changes


def rejection_feedback(error, context, remaining):
    return {
        'status': 'rejected', 'error': error,
        'remaining_proposal_attempts': remaining,
        'context_state': context.remaining_payload(),
        'repair_instruction': 'Correct the reported field/constraint only; retain valid choices. '
            'Previously disclosed information is already in the conversation. '
            'Do not request it again or relax user requirements.',
    }
