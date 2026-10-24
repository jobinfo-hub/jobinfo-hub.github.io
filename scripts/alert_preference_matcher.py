"""Safety-first matching of CareerPick ALIO jobs against OneSignal user tags.

No network requests or notification sending. All selected dimensions use AND
across dimensions and OR within each dimension. Unknown fields do not match.
"""
import re

DIMENSIONS = {
    "region": ("region", "cp2_region_"),
    "employment": ("emp", "cp2_employment_"),
    "education": ("edu", "cp2_education_"),
    "category": ("cat", "cp2_category_"),
}

def tokens(value):
    if isinstance(value, list):
        return [str(v).strip().casefold() for v in value if str(v).strip()]
    return [str(value).strip().casefold()] if value is not None and str(value).strip() else []

def selected(tags, prefix):
    return [str(tags.get(prefix + str(i), "")).strip().casefold()
            for i in range(1, 6) if str(tags.get(prefix + str(i), "")).strip()]

def matches(job, tags):
    if str(tags.get("cp_preferences_set", "")).lower() != "yes":
        return False
    if str(tags.get("cp_schema", "")) != "2":
        return False
    for _, (job_key, prefix) in DIMENSIONS.items():
        wants = selected(tags, prefix)
        if wants and not set(wants).intersection(tokens(job.get(job_key))):
            return False
    keywords = [s.strip().casefold() for s in re.split(r"[,，]", str(tags.get("cp_keywords", ""))) if s.strip()]
    if keywords:
        text = " ".join(str(job.get(k) or "") for k in ("title", "org", "desc", "text")).casefold()
        if not any(word in text for word in keywords):
            return False
    return True
