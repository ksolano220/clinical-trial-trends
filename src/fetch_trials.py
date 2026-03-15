"""
Fetch clinical trial data from ClinicalTrials.gov API v2.

Pulls study metadata in batches and saves as a flat CSV for analysis.
No API key required.
"""

import csv
import time
from pathlib import Path

import requests

BASE_URL = "https://clinicaltrials.gov/api/v2/studies"
OUTPUT_PATH = Path("data/clinical_trials.csv")
MAX_STUDIES = 10000
PAGE_SIZE = 100

FIELDS = [
    "nct_id", "brief_title", "overall_status", "phase", "study_type",
    "start_date", "completion_date", "enrollment",
    "condition", "lead_sponsor", "sponsor_type",
    "country",
]


def parse_study(study):
    proto = study.get("protocolSection", {})
    ident = proto.get("identificationModule", {})
    status = proto.get("statusModule", {})
    design = proto.get("designModule", {})
    sponsor_mod = proto.get("sponsorCollaboratorsModule", {})
    lead = sponsor_mod.get("leadSponsor", {})
    conditions_mod = proto.get("conditionsModule", {})
    contacts = proto.get("contactsLocationsModule", {})

    phases = design.get("phases", [])
    phase_str = phases[0] if phases else ""

    conditions = conditions_mod.get("conditions", [])
    condition_str = conditions[0] if conditions else ""

    locations = contacts.get("locations", [])
    countries = list(set(loc.get("country", "") for loc in locations if loc.get("country")))
    country_str = countries[0] if len(countries) == 1 else "|".join(sorted(countries)[:5])

    enrollment_info = design.get("enrollmentInfo", {})

    return {
        "nct_id": ident.get("nctId", ""),
        "brief_title": ident.get("briefTitle", ""),
        "overall_status": status.get("overallStatus", ""),
        "phase": phase_str,
        "study_type": design.get("studyType", ""),
        "start_date": status.get("startDateStruct", {}).get("date", ""),
        "completion_date": status.get("completionDateStruct", {}).get("date", ""),
        "enrollment": enrollment_info.get("count", ""),
        "condition": condition_str,
        "lead_sponsor": lead.get("name", ""),
        "sponsor_type": lead.get("class", ""),
        "country": country_str,
    }


def fetch():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    if OUTPUT_PATH.exists():
        size_mb = OUTPUT_PATH.stat().st_size / (1024 * 1024)
        print(f"Data already exists ({size_mb:.1f} MB): {OUTPUT_PATH}")
        return

    print(f"Fetching up to {MAX_STUDIES:,} studies from ClinicalTrials.gov...")

    all_rows = []
    next_token = None
    fetched = 0

    while fetched < MAX_STUDIES:
        params = {
            "format": "json",
            "pageSize": PAGE_SIZE,
        }
        if next_token:
            params["pageToken"] = next_token

        resp = requests.get(BASE_URL, params=params)
        resp.raise_for_status()
        data = resp.json()

        studies = data.get("studies", [])
        if not studies:
            break

        for study in studies:
            all_rows.append(parse_study(study))

        fetched += len(studies)
        next_token = data.get("nextPageToken")
        print(f"\r  Fetched {fetched:,} studies", end="", flush=True)

        if not next_token:
            break

        time.sleep(0.3)

    print()

    with open(OUTPUT_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f"Saved {len(all_rows):,} studies → {OUTPUT_PATH}")


if __name__ == "__main__":
    fetch()
