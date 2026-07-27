import re
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Optional


@dataclass
class DateForensicFinding:
    check_type: str
    passed: bool
    detail: str
    confidence: str = "medium"
    doc_a: Optional[str] = None
    doc_b: Optional[str] = None
    val_a: Optional[str] = None
    val_b: Optional[str] = None


DATE_PATTERNS = [
    re.compile(r'(\d{4})-(\d{2})-(\d{2})'),
    re.compile(r'(\d{2})[\/-](\d{2})[\/-](\d{4})'),
]


def _parse_date(val) -> Optional[datetime]:
    if val is None:
        return None
    s = str(val).strip()
    for pat in DATE_PATTERNS:
        m = pat.search(s)
        if m:
            groups = m.groups()
            if len(groups[0]) == 4:
                y, mth, d = int(groups[0]), int(groups[1]), int(groups[2])
            else:
                d, mth, y = int(groups[0]), int(groups[1]), int(groups[2])
            try:
                return datetime(y, mth, d)
            except ValueError:
                return None
    return None


def _get_field(extracted_by_doc: dict, doc_name: str, field: str) -> Optional[str]:
    doc_fields = extracted_by_doc.get(doc_name, {})
    entry = doc_fields.get(field)
    if isinstance(entry, dict):
        return str(entry.get("value", ""))
    if entry is not None:
        return str(entry)
    return None


def check_future_dates(extracted_by_doc: dict) -> list[DateForensicFinding]:
    findings = []
    now = datetime.now()
    date_fields = [
        ("kyc", "dob"), ("death_certificate", "date_of_death"),
        ("death_certificate", "registration_date"), ("legal_heir", "date_of_death"),
        ("plan_approval", "sanction_date"), ("occupancy_cert", "completion_date"),
        ("appointment", "joining_date"), ("appointment", "date_of_appointment"),
        ("roc_certificate", "incorporation_date"), ("rera", "completion_date"),
    ]
    for doc_name, field in date_fields:
        val = _get_field(extracted_by_doc, doc_name, field)
        parsed = _parse_date(val)
        if parsed and parsed > now:
            findings.append(DateForensicFinding(
                check_type="future_date", passed=False,
                detail=f"{doc_name}/{field} has future date: {val}",
                confidence="high", doc_a=doc_name, val_a=val))
        elif parsed and parsed.year < 1900:
            findings.append(DateForensicFinding(
                check_type="implausible_date", passed=False,
                detail=f"{doc_name}/{field} has implausibly old date: {val}",
                confidence="high", doc_a=doc_name, val_a=val))
    return findings


def check_chronological_chain(extracted_by_doc: dict) -> list[DateForensicFinding]:
    findings = []

    dob = _parse_date(_get_field(extracted_by_doc, "kyc", "dob"))
    dod_dc = _parse_date(_get_field(extracted_by_doc, "death_certificate", "date_of_death"))
    dod_lh = _parse_date(_get_field(extracted_by_doc, "legal_heir", "date_of_death"))
    reg_date = _parse_date(_get_field(extracted_by_doc, "death_certificate", "registration_date"))
    sanction_date = _parse_date(_get_field(extracted_by_doc, "plan_approval", "sanction_date"))
    completion_date = _parse_date(_get_field(extracted_by_doc, "occupancy_cert", "completion_date"))
    inc_date = _parse_date(_get_field(extracted_by_doc, "roc_certificate", "incorporation_date"))
    joining = _parse_date(_get_field(extracted_by_doc, "appointment", "joining_date"))
    dob_dc_v = _get_field(extracted_by_doc, "death_certificate", "deceased_dob")
    dod_dc_v = _get_field(extracted_by_doc, "death_certificate", "date_of_death")
    dob_dc_parsed = _parse_date(dob_dc_v)

    if dod_dc and reg_date and dod_dc > reg_date:
        findings.append(DateForensicFinding(
            check_type="death_before_registration", passed=False,
            detail=f"Death date ({dod_dc_v}) is after registration date , impossible",
            confidence="high", doc_a="death_certificate", val_a=dod_dc_v, doc_b="death_certificate", val_b=_get_field(extracted_by_doc, "death_certificate", "registration_date")))

    if dod_dc and dod_lh and dod_dc != dod_lh:
        d1 = _get_field(extracted_by_doc, "death_certificate", "date_of_death")
        d2 = _get_field(extracted_by_doc, "legal_heir", "date_of_death")
        findings.append(DateForensicFinding(
            check_type="death_date_mismatch", passed=False,
            detail=f"Death date differs between death certificate ({d1}) and legal heir ({d2})",
            confidence="high", doc_a="death_certificate", val_a=d1, doc_b="legal_heir", val_b=d2))

    if dob_dc_parsed and dod_dc:
        age = (dod_dc - dob_dc_parsed).days / 365.25
        if age > 120:
            findings.append(DateForensicFinding(
                check_type="age_at_death_implausible", passed=False,
                detail=f"Age at death ({age:.0f} years) is implausible",
                confidence="high", doc_a="death_certificate", val_a=dob_dc_v, doc_b="death_certificate", val_b=dod_dc_v))
        elif age < 0:
            findings.append(DateForensicFinding(
                check_type="death_before_birth", passed=False,
                detail=f"Death date is before date of birth , impossible",
                confidence="high", doc_a="death_certificate", val_a=dob_dc_v, doc_b="death_certificate", val_b=dod_dc_v))

    if dob and dob_dc_parsed and dob != dob_dc_parsed:
        dob_v = _get_field(extracted_by_doc, "kyc", "dob")
        dod_v = _get_field(extracted_by_doc, "death_certificate", "date_of_death")
        findings.append(DateForensicFinding(
            check_type="dob_kyc_vs_death_cert", passed=False,
            detail=f"DOB differs between KYC ({dob_v}) and death certificate ({dob_dc_v})",
            confidence="high", doc_a="kyc", val_a=dob_v, doc_b="death_certificate", val_b=dob_dc_v))

    if sanction_date and completion_date and completion_date < sanction_date:
        s_v = _get_field(extracted_by_doc, "plan_approval", "sanction_date")
        c_v = _get_field(extracted_by_doc, "occupancy_cert", "completion_date")
        findings.append(DateForensicFinding(
            check_type="completion_before_sanction", passed=False,
            detail=f"Occupancy completion ({c_v}) is before plan sanction date ({s_v}) , impossible",
            confidence="high", doc_a="plan_approval", val_a=s_v, doc_b="occupancy_cert", val_b=c_v))

    if inc_date and joining and joining < inc_date:
        i_v = _get_field(extracted_by_doc, "roc_certificate", "incorporation_date")
        j_v = _get_field(extracted_by_doc, "appointment", "joining_date")
        findings.append(DateForensicFinding(
            check_type="joining_before_incorporation", passed=False,
            detail=f"Joining date ({j_v}) is before company incorporation ({i_v}) , impossible",
            confidence="high", doc_a="roc_certificate", val_a=i_v, doc_b="appointment", val_b=j_v))

    return findings


def check_appointment_tenure(extracted_by_doc: dict) -> list[DateForensicFinding]:
    findings = []
    joining = _parse_date(_get_field(extracted_by_doc, "appointment", "joining_date"))
    app_date = _parse_date(_get_field(extracted_by_doc, "appointment", "date_of_appointment"))
    tenure_str = _get_field(extracted_by_doc, "appointment", "tenure_months")

    if joining and app_date and joining != app_date:
        jv = _get_field(extracted_by_doc, "appointment", "joining_date")
        av = _get_field(extracted_by_doc, "appointment", "date_of_appointment")
        findings.append(DateForensicFinding(
            check_type="appointment_date_mismatch", passed=False,
            detail=f"Joining date ({jv}) differs from appointment date ({av})",
            confidence="medium", doc_a="appointment", val_a=jv, doc_b="appointment", val_b=av))

    if tenure_str:
        try:
            tenure = int(re.sub(r'[^0-9]', '', str(tenure_str)))
            if tenure < 0 or tenure > 600:
                findings.append(DateForensicFinding(
                    check_type="implausible_tenure", passed=False,
                    detail=f"Appointment tenure ({tenure} months) is implausible",
                    confidence="high", doc_a="appointment", val_a=tenure_str))
        except ValueError:
            pass

    return findings


def analyze_all_dates(extracted_by_doc: dict) -> list[DateForensicFinding]:
    findings = []
    findings.extend(check_future_dates(extracted_by_doc))
    findings.extend(check_chronological_chain(extracted_by_doc))
    findings.extend(check_appointment_tenure(extracted_by_doc))
    return findings
