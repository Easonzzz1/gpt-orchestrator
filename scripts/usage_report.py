#!/usr/bin/env python3
"""Summarize local API usage JSONL; never call a service or infer prices."""
import argparse
import json
import math
import sys
from pathlib import Path


def count(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(name + ' must be a non-negative integer')
    return value


def normalize(record):
    if not isinstance(record, dict) or not isinstance(record.get('usage'), dict):
        raise ValueError('each record must contain a usage object')
    usage = record['usage']
    responses = 'input_tokens' in usage
    chat = 'prompt_tokens' in usage
    if responses == chat:
        raise ValueError('use exactly one API usage field family')
    input_key, output_key, details_key = (
        ('input_tokens', 'output_tokens', 'input_tokens_details') if responses
        else ('prompt_tokens', 'completion_tokens', 'prompt_tokens_details'))
    input_count = count(usage.get(input_key), input_key)
    output_count = count(usage.get(output_key), output_key)
    details = usage.get(details_key)
    if details is None:
        details = {}
    if not isinstance(details, dict):
        raise ValueError('input token details must be an object or null')
    cached = details.get('cached_tokens')
    written = details.get('cache_write_tokens')
    for key, value in [('cached_tokens', cached), ('cache_write_tokens', written)]:
        if value is not None and count(value, key) > input_count:
            raise ValueError(key + ' exceeds input tokens')
    if cached is not None and written is not None and cached + written > input_count:
        raise ValueError('cache read and write tokens exceed input tokens')
    latency = record.get('latency_ms')
    if latency is not None and (type(latency) not in (int, float)
                                or not math.isfinite(latency) or latency < 0):
        raise ValueError('latency_ms must be finite and non-negative')
    return dict(input_tokens=input_count, output_tokens=output_count,
                cached_tokens=cached, cache_write_tokens=written, latency_ms=latency)


def summarize(records):
    rows = [normalize(row) for row in records]
    if not rows:
        raise ValueError('no usage records found')
    inputs = sum(row['input_tokens'] for row in rows)
    known_cache = [row for row in rows if row['cached_tokens'] is not None]
    cache_inputs = sum(row['input_tokens'] for row in known_cache)
    cached = sum(row['cached_tokens'] for row in known_cache)
    writes = [row['cache_write_tokens'] for row in rows if row['cache_write_tokens'] is not None]
    latencies = [row['latency_ms'] for row in rows if row['latency_ms'] is not None]
    return dict(
        records=len(rows), input_tokens=inputs,
        output_tokens=sum(row['output_tokens'] for row in rows),
        cached_tokens_known=cached, cache_records_known=len(known_cache),
        cache_records_unknown=len(rows) - len(known_cache),
        cache_ratio_on_known_input=cached / cache_inputs if cache_inputs else None,
        cache_ratio_all_input=(cached / inputs if inputs else None)
        if len(known_cache) == len(rows) else None,
        cache_write_tokens_known=sum(writes), cache_write_records_known=len(writes),
        latency_records_known=len(latencies),
        latency_ms_mean=sum(latencies) / len(latencies) if latencies else None,
        cost=None, subscription_quota_savings=None,
    )


def read_records(path):
    records = []
    with Path(path).open(encoding='utf-8') as source:
        for line_number, line in enumerate(source, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
                normalize(record)
                records.append(record)
            except (ValueError, TypeError) as error:
                # Do not echo a response, task text, private path or invalid value.
                raise ValueError('invalid usage record at line {}'.format(line_number)) from error
    return records


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', help='local JSONL containing one usage object per line')
    args = parser.parse_args(argv)
    try:
        result = summarize(read_records(args.file))
    except (OSError, ValueError, TypeError):
        print('Could not summarize usage: check file access and usage schema. No partial report produced.', file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
