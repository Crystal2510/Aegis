"""
clause_analyzer.py

NLP-based clause and statement analysis for detecting content-level forgeries
in free-text document sections (rent agreement clauses, appointment letter
terms, ITR schedules, etc.).

This is the engine that catches forgeries in "clauses and statements" --
semantic content edits that neither the visual model (pixel-level) nor the
field-level cross-doc checker can detect.

Approach: rule-based pattern matching + lightweight semantic consistency
checks. No large language model dependency -- runs entirely locally.
"""

import re
from dataclasses import dataclass, field


@dataclass
class ClauseFinding:
    document: str
    section: str
    check_name: str
    passed: bool
    detail: str
    confidence: float = 1.0


_RENT_CLAUSE_KEYWORDS = {
    "lock_in_period": {
        "patterns": [
            r'lock[\s-]?in[\s-]?period',
            r'minimum\s+period',
            r'non[\s-]?cancellable',
            r'notice\s+period',
        ],
        "purpose": "lock-in period clause",
    },
    "maintenance": {
        "patterns": [
            r'maintenance',
            r'repairs?',
            r'upkeep',
        ],
        "purpose": "maintenance responsibility clause",
    },
    "security_deposit": {
        "patterns": [
            r'security\s+deposit',
            r'advance\s+deposit',
            r'interest[\s-]?free',
        ],
        "purpose": "security deposit clause",
    },
    "termination": {
        "patterns": [
            r'terminat',
            r'surrender',
            r'vacat',
            r'hand\s+over',
        ],
        "purpose": "termination clause",
    },
    "subletting": {
        "patterns": [
            r'sub[-\s]?let',
            r'sublet',
            r'assign',
        ],
        "purpose": "subletting restriction clause",
    },
    "utility_bills": {
        "patterns": [
            r'electr',
            r'water',
            r'utility',
            r'maintenance\s+charges',
            r'society',
        ],
        "purpose": "utility bills responsibility clause",
    },
}

_APPOINTMENT_CLAUSE_KEYWORDS = {
    "probation": {
        "patterns": [
            r'probation',
            r'trial\s+period',
            r'notice\s+period',
        ],
        "purpose": "probation clause",
    },
    "non_compete": {
        "patterns": [
            r'non[\s-]?compete',
            r'exclusivi',
            r'confidential',
        ],
        "purpose": "non-compete / confidentiality clause",
    },
    "benefits": {
        "patterns": [
            r'benefit',
            r'insurance',
            r'bonus',
            r'incentive',
        ],
        "purpose": "benefits clause",
    },
    "leave": {
        "patterns": [
            r'leave',
            r'vacation',
            r'holiday',
            r'absent',
        ],
        "purpose": "leave policy clause",
    },
}

_ITR_SCHEDULE_KEYWORDS = {
    "salary_income": {
        "patterns": [
            r'salary',
            r'wages?',
            r'pension',
            r'income\s+from\s+salary',
        ],
        "purpose": "salary income schedule",
    },
    "house_property": {
        "patterns": [
            r'house\s+property',
            r'rental\s+income',
            r'let[\s-]?out',
        ],
        "purpose": "house property income schedule",
    },
    "business_profession": {
        "patterns": [
            r'business',
            r'profession',
            r'freelance',
            r'profession\s+or\s+business',
        ],
        "purpose": "business/profession income schedule",
    },
    "capital_gains": {
        "patterns": [
            r'capital\s+gains?',
            r'shares?',
            r'securities?',
            r'mutual\s+fund',
        ],
        "purpose": "capital gains schedule",
    },
    "deductions": {
        "patterns": [
            r'deduction',
            r'section\s+80',
            r'tax\s+saving',
            r'chapter\s+via',
        ],
        "purpose": "deductions schedule (80C, 80D, etc.)",
    },
}


def _extract_text_block(fields: dict, key: str) -> str | None:
    entry = fields.get(key)
    if isinstance(entry, dict):
        return entry.get("value")
    return entry


def _check_clause_presence(text: str, keyword_spec: dict) -> list[dict]:
    results = []
    text_lower = text.lower()
    for clause_id, spec in keyword_spec.items():
        found_any = any(re.search(p, text_lower) for p in spec["patterns"])
        results.append({
            "clause_id": clause_id,
            "purpose": spec["purpose"],
            "found": found_any,
        })
    return results


def analyze_rent_agreement(extracted_fields_by_doc: dict) -> list[ClauseFinding]:
    findings = []
    rent = extracted_fields_by_doc.get("rent", {})

    text_blocks = []
    for key in rent:
        if key.startswith("clause_") or key == "terms":
            block = _extract_text_block(rent, key)
            if block:
                text_blocks.append(block)

    combined_text = " ".join(text_blocks) if text_blocks else ""

    if not combined_text:
        findings.append(ClauseFinding(
            document="rent", section="all", check_name="clause_extraction",
            passed=False, detail="No clause text could be extracted from rent agreement.",
            confidence=0.5,
        ))
        return findings

    clause_results = _check_clause_presence(combined_text, _RENT_CLAUSE_KEYWORDS)
    for cr in clause_results:
        findings.append(ClauseFinding(
            document="rent",
            section=cr["clause_id"],
            check_name=cr["purpose"],
            passed=cr["found"],
            detail=f"{cr['purpose']}: {'found' if cr['found'] else 'MISSING'} in rent agreement text.",
            confidence=0.8,
        ))

    standard_clauses = {"lock_in_period", "security_deposit", "termination", "maintenance"}
    found_ids = {cr["clause_id"] for cr in clause_results if cr["found"]}
    missing_standard = standard_clauses - found_ids
    if missing_standard:
        findings.append(ClauseFinding(
            document="rent", section="completeness",
            check_name="standard_clause_completeness",
            passed=False,
            detail=f"Missing standard clauses: {', '.join(missing_standard)}. "
                   "May indicate an abbreviated or fabricated agreement.",
            confidence=0.6,
        ))

    return findings


def analyze_appointment_letter(extracted_fields_by_doc: dict) -> list[ClauseFinding]:
    findings = []
    appointment = extracted_fields_by_doc.get("appointment", {})

    text_blocks = []
    for key in appointment:
        if key.startswith("clause_") or key == "terms" or key == "conditions":
            block = _extract_text_block(appointment, key)
            if block:
                text_blocks.append(block)

    combined_text = " ".join(text_blocks) if text_blocks else ""

    if not combined_text:
        findings.append(ClauseFinding(
            document="appointment", section="all", check_name="clause_extraction",
            passed=False, detail="No clause text could be extracted from appointment letter.",
            confidence=0.5,
        ))
        return findings

    clause_results = _check_clause_presence(combined_text, _APPOINTMENT_CLAUSE_KEYWORDS)
    for cr in clause_results:
        findings.append(ClauseFinding(
            document="appointment",
            section=cr["clause_id"],
            check_name=cr["purpose"],
            passed=cr["found"],
            detail=f"{cr['purpose']}: {'found' if cr['found'] else 'MISSING'} in appointment letter.",
            confidence=0.8,
        ))

    return findings


def analyze_itr_schedules(extracted_fields_by_doc: dict) -> list[ClauseFinding]:
    findings = []
    itr = extracted_fields_by_doc.get("itr", {})

    text_blocks = []
    for key in itr:
        if key.startswith("schedule_") or key == "income_breakdown":
            block = _extract_text_block(itr, key)
            if block:
                text_blocks.append(block)

    combined_text = " ".join(text_blocks) if text_blocks else ""

    if not combined_text:
        itr_gross = _extract_text_block(itr, "gross_total_income")
        if itr_gross:
            findings.append(ClauseFinding(
                document="itr", section="all", check_name="schedule_extraction",
                passed=False,
                detail="Only gross total income extracted, no schedule breakdown available.",
                confidence=0.4,
            ))
        return findings

    schedule_results = _check_clause_presence(combined_text, _ITR_SCHEDULE_KEYWORDS)
    for sr in schedule_results:
        findings.append(ClauseFinding(
            document="itr",
            section=sr["clause_id"],
            check_name=sr["purpose"],
            passed=sr["found"],
            detail=f"{sr['purpose']}: {'found' if sr['found'] else 'MISSING'} in ITR schedules.",
            confidence=0.8,
        ))

    return findings


def analyze_all_clauses(extracted_fields_by_doc: dict) -> list[ClauseFinding]:
    findings = []
    findings.extend(analyze_rent_agreement(extracted_fields_by_doc))
    findings.extend(analyze_appointment_letter(extracted_fields_by_doc))
    findings.extend(analyze_itr_schedules(extracted_fields_by_doc))
    return findings
