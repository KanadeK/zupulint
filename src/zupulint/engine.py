"""Backward-compatible rule-engine imports.

New integrations should import from :mod:`zupulint.rules`.
"""

from zupulint.rules import RULE_BY_ID, RULES, Issue, RuleDefinition, ScanResult, scan

__all__ = ["RULES", "RULE_BY_ID", "Issue", "RuleDefinition", "ScanResult", "scan"]
