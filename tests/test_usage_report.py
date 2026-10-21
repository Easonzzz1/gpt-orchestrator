import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'usage_report.py'
spec = importlib.util.spec_from_file_location('usage_report', SCRIPT)
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def row(inputs=10, cached=4):
    return {'usage': {'input_tokens': inputs, 'output_tokens': 2,
                      'input_tokens_details': {'cached_tokens': cached}}}


class UsageReportTests(unittest.TestCase):
    def test_weighted_cache_ratio_and_total_input(self):
        result = report.summarize([row(10, 5), row(90, 0)])
        self.assertEqual(result['input_tokens'], 100)
        self.assertEqual(result['cache_ratio_all_input'], .05)
        self.assertIsNone(result['cost'])
        self.assertIsNone(result['subscription_quota_savings'])

    def test_unknown_cache_is_not_zero(self):
        result = report.summarize([row(), row(90, None)])
        self.assertIsNone(result['cache_ratio_all_input'])
        self.assertEqual(result['cache_ratio_on_known_input'], .4)
        self.assertEqual(result['cache_records_unknown'], 1)

    def test_chat_usage_and_zero_denominator(self):
        result = report.summarize([{'usage': {'prompt_tokens': 0, 'completion_tokens': 0,
                                            'prompt_tokens_details': {'cached_tokens': 0}}}])
        self.assertIsNone(result['cache_ratio_all_input'])

    def test_invalid_counts_and_inconsistent_cache(self):
        for value in [-1, True, 1.5, '10']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                report.normalize(row(value))
        bad = row(10, 8)
        bad['usage']['input_tokens_details']['cache_write_tokens'] = 3
        with self.assertRaises(ValueError):
            report.normalize(bad)
        with self.assertRaises(ValueError):
            report.normalize(row(10, 11))

    def test_missing_mixed_fields_and_latency(self):
        for value in [{}, {'usage': {}}, {'usage': {'input_tokens': 1, 'prompt_tokens': 1}}]:
            with self.assertRaises(ValueError):
                report.normalize(value)
        for latency in [True, float('nan'), float('inf'), -1]:
            bad = row()
            bad['latency_ms'] = latency
            with self.assertRaises(ValueError):
                report.normalize(bad)

    def test_cli_rejects_entire_file_without_echoing_data(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'private.jsonl'
            path.write_text(json.dumps(row()) + '\nPRIVATE-TASK-EXAMPLE\n')
            proc = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(proc.stdout, '')
        self.assertNotIn('PRIVATE-TASK-EXAMPLE', proc.stderr)
        self.assertNotIn(str(path), proc.stderr)

    def test_synthetic_fixture(self):
        result = report.summarize(report.read_records(SCRIPT.parents[1] / 'examples' / 'usage.synthetic.jsonl'))
        self.assertEqual(result['input_tokens'], 30000)
        self.assertEqual(result['output_tokens'], 1500)
        self.assertEqual(result['cache_ratio_all_input'], .4)
        self.assertEqual(result['cache_write_tokens_known'], 10000)


if __name__ == '__main__':
    unittest.main()
