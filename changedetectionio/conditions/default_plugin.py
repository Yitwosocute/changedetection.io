import re

import pluggy
from price_parser import Price
from loguru import logger

hookimpl = pluggy.HookimplMarker("changedetectionio_conditions")


def _coerce_float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _extract_number_from_text(text):
    if not text:
        return None
    price = Price.fromstring(text)
    if price and price.amount is not None:
        return _coerce_float(price.amount)
    return None


def _extract_previous_number_from_watch(watch):
    try:
        keys = list(watch.history.keys())
    except Exception:
        return None

    if not keys:
        return None

    latest_key = keys[-1]
    try:
        snapshot_text = watch.get_history_snapshot(latest_key)
    except Exception as e:
        logger.debug(f"Unable to read previous snapshot for conditions: {str(e)}")
        return None

    return _extract_number_from_text(snapshot_text)


def _delta_comparison(data, current_value, threshold, expect_increase=True):
    current = _coerce_float(current_value)
    previous = _coerce_float((data or {}).get('extracted_number_previous'))
    limit = _coerce_float(threshold)

    if current is None or previous is None or limit is None:
        return False

    delta = current - previous
    return delta > limit if expect_increase else (previous - current) > limit


@hookimpl
def register_operators():
    def starts_with(_, text, prefix):
        return text.lower().strip().startswith(str(prefix).strip().lower())

    def ends_with(_, text, suffix):
        return text.lower().strip().endswith(str(suffix).strip().lower())

    def length_min(_, text, strlen):
        return len(text) >= int(strlen)

    def length_max(_, text, strlen):
        return len(text) <= int(strlen)

    # Custom function for case-insensitive regex matching
    def contains_regex(_, text, pattern):
        """Returns True if `text` contains `pattern` (case-insensitive regex match)."""
        return bool(re.search(pattern, str(text), re.IGNORECASE))

    # Custom function for NOT matching case-insensitive regex
    def not_contains_regex(_, text, pattern):
        """Returns True if `text` does NOT contain `pattern` (case-insensitive regex match)."""
        return not bool(re.search(pattern, str(text), re.IGNORECASE))

    def not_contains(_, text, pattern):
        return not pattern in text

    def number_increase_more_than(data, current_value, threshold):
        return _delta_comparison(data, current_value, threshold, expect_increase=True)

    def number_decrease_more_than(data, current_value, threshold):
        return _delta_comparison(data, current_value, threshold, expect_increase=False)

    return {
        "!in": not_contains,
        "!contains_regex": not_contains_regex,
        "contains_regex": contains_regex,
        "ends_with": ends_with,
        "length_max": length_max,
        "length_min": length_min,
        "starts_with": starts_with,
        "number_increase_gt": number_increase_more_than,
        "number_decrease_gt": number_decrease_more_than,
    }

@hookimpl
def register_operator_choices():
    return [
        ("!in", "Does NOT Contain"),
        ("starts_with", "Text Starts With"),
        ("ends_with", "Text Ends With"),
        ("length_min", "Length minimum"),
        ("length_max", "Length maximum"),
        ("contains_regex", "Text Matches Regex"),
        ("!contains_regex", "Text Does NOT Match Regex"),
        ("number_increase_gt", "Has number that increased more than (+Δ >)"),
        ("number_decrease_gt", "Has number that decreased more than (-Δ >)"),
    ]

@hookimpl
def register_field_choices():
    return [
        ("extracted_number", "Extracted number after 'Filters & Triggers'"),
#        ("meta_description", "Meta Description"),
#        ("meta_keywords", "Meta Keywords"),
        ("page_filtered_text", "Page text after 'Filters & Triggers'"),
        #("page_title", "Page <title>"), # actual page title <title>
    ]

@hookimpl
def add_data(current_watch_uuid, application_datastruct, ephemeral_data):

    res = {}
    watch = application_datastruct['watching'].get(current_watch_uuid)
    if 'text' in ephemeral_data:
        res['page_filtered_text'] = ephemeral_data['text']
        current_number = _extract_number_from_text(ephemeral_data.get('text'))
        if current_number is not None:
            res['extracted_number'] = current_number
            logger.debug(f"Extracted number result returning float({res['extracted_number']})")

    if watch:
        previous_number = _extract_previous_number_from_watch(watch)
        if previous_number is not None:
            res['extracted_number_previous'] = previous_number

    return res
