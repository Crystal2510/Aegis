import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class PropertyForensicFinding:
    check_type: str
    passed: bool
    detail: str
    confidence: str = "medium"
    doc_a: Optional[str] = None
    doc_b: Optional[str] = None
    val_a: Optional[str] = None
    val_b: Optional[str] = None


def _get_field(extracted_by_doc: dict, doc_name: str, field: str) -> Optional[str]:
    doc_fields = extracted_by_doc.get(doc_name, {})
    entry = doc_fields.get(field)
    if isinstance(entry, dict):
        return str(entry.get("value", ""))
    if entry is not None:
        return str(entry)
    return None


def check_rera_format(extracted_by_doc: dict) -> list[PropertyForensicFinding]:
    findings = []
    rera = _get_field(extracted_by_doc, "rera", "rera_number")
    if rera:
        clean = str(rera).strip()
        if re.match(r'^[A-Z]{2}/RERA/\d{4}/\d{5,10}$', clean, re.IGNORECASE):
            findings.append(PropertyForensicFinding(
                check_type="rera_format", passed=True,
                detail=f"RERA number '{clean}' matches standard format", confidence="high"))
        elif re.match(r'^[A-Z]{2}/\d{2,6}/\d{4,10}$', clean, re.IGNORECASE):
            findings.append(PropertyForensicFinding(
                check_type="rera_format", passed=False,
                detail=f"RERA number '{clean}' has non-standard format (expected: XX/RERA/YYYY/XXXXX)",
                confidence="medium", doc_a="rera", val_a=clean))
        else:
            findings.append(PropertyForensicFinding(
                check_type="rera_format", passed=False,
                detail=f"RERA number '{clean}' does not match any known format",
                confidence="high", doc_a="rera", val_a=clean))
    else:
        findings.append(PropertyForensicFinding(
            check_type="rera_format", passed=True,
            detail="RERA number not available for validation", confidence="low"))
    return findings


def check_builder_project_consistency(extracted_by_doc: dict) -> list[PropertyForensicFinding]:
    findings = []
    builder_rera = _get_field(extracted_by_doc, "rera", "promoter_name")
    builder_pa = _get_field(extracted_by_doc, "plan_approval", "builder_name")
    builder_oc = _get_field(extracted_by_doc, "occupancy_cert", "builder_name")
    project_rera = _get_field(extracted_by_doc, "rera", "project_name")
    project_pa = _get_field(extracted_by_doc, "plan_approval", "project_name")
    project_oc = _get_field(extracted_by_doc, "occupancy_cert", "project_name")

    builder_pairs = [("rera", builder_rera, "plan_approval", builder_pa),
                     ("rera", builder_rera, "occupancy_cert", builder_oc),
                     ("plan_approval", builder_pa, "occupancy_cert", builder_oc)]
    project_pairs = [("rera", project_rera, "plan_approval", project_pa),
                     ("rera", project_rera, "occupancy_cert", project_oc),
                     ("plan_approval", project_pa, "occupancy_cert", project_oc)]

    for doc_a, val_a, doc_b, val_b in builder_pairs:
        if isinstance(val_a, str) and isinstance(val_b, str) and val_a.strip().lower() != val_b.strip().lower():
            findings.append(PropertyForensicFinding(
                check_type="builder_name_mismatch", passed=False,
                detail=f"Builder/promoter name differs: {doc_a}='{val_a}' vs {doc_b}='{val_b}'",
                confidence="high", doc_a=doc_a, val_a=val_a, doc_b=doc_b, val_b=val_b))

    for doc_a, val_a, doc_b, val_b in project_pairs:
        if isinstance(val_a, str) and isinstance(val_b, str) and val_a.strip().lower() != val_b.strip().lower():
            findings.append(PropertyForensicFinding(
                check_type="project_name_mismatch", passed=False,
                detail=f"Project name differs: {doc_a}='{val_a}' vs {doc_b}='{val_b}'",
                confidence="high", doc_a=doc_a, val_a=val_a, doc_b=doc_b, val_b=val_b))

    if not any(f.check_type in ("builder_name_mismatch", "project_name_mismatch") and not f.passed for f in findings):
        findings.append(PropertyForensicFinding(
            check_type="builder_project_consistency", passed=True,
            detail="Builder/promoter and project names consistent across property documents",
            confidence="high"))

    return findings


def analyze_property_documents(extracted_by_doc: dict) -> list[PropertyForensicFinding]:
    findings = []
    findings.extend(check_rera_format(extracted_by_doc))
    findings.extend(check_builder_project_consistency(extracted_by_doc))
    return findings
