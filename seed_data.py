import random
import uuid
from datetime import datetime, timedelta
from google.cloud import bigquery

PROJECT_ID = "ottawa-police-496223"
DATASET    = "ops_intelligence"
TABLE      = "incidents"

DISTRICTS = ["Central", "East", "West", "South", "North", "Rideau-Rockcliffe"]
NEIGHBOURHOODS = {
    "Central":           ["ByWard Market", "Centretown", "Lowertown", "Vanier"],
    "East":              ["Orleans", "Blackburn Hamlet", "Cumberland", "Beacon Hill"],
    "West":              ["Kanata", "Stittsville", "Bells Corners", "Barrhaven"],
    "South":             ["Carleton Heights", "Heron Gate", "Hunt Club", "Riverside South"],
    "North":             ["Manor Park", "New Edinburgh", "Rockcliffe Park", "Lindenlea"],
    "Rideau-Rockcliffe": ["Overbrook", "East Wellington", "Eastview", "Riverview"],
}
INCIDENT_TYPES = ["Theft", "Assault", "Vandalism", "Break_Enter", "Fraud", "Mischief", "Robbery"]
SEVERITIES     = ["LOW", "LOW", "MEDIUM", "MEDIUM", "MEDIUM", "HIGH", "CRITICAL"]
STATUSES       = ["OPEN", "UNDER_INVESTIGATION", "CLOSED", "CLOSED", "CLOSED"]
DESCRIPTIONS   = [
    "Suspect fled on foot before officers arrived.",
    "Victim reported incident several hours after occurrence.",
    "CCTV footage secured and under review.",
    "Multiple witnesses interviewed at scene.",
    "Suspect arrested and held for bail hearing.",
    "Officers responded; no suspects identified at scene.",
    "Matter referred to detective division for follow-up.",
    "Electronic evidence retrieved and sent to forensics.",
]

def generate(n=500):
    records = []
    now = datetime.utcnow()
    for _ in range(n):
        days_ago = random.randint(0, 90)
        ts = now - timedelta(days=days_ago, hours=random.randint(0,23), minutes=random.randint(0,59))
        district = random.choice(DISTRICTS)
        # Deliberate spike in Central last 7 days — anomaly detector will catch this
        if days_ago <= 7 and random.random() < 0.45:
            district = "Central"
        neighbourhood = random.choice(NEIGHBOURHOODS[district])
        status = random.choice(STATUSES)
        records.append({
            "incident_id":       f"INC-{str(uuid.uuid4())[:8].upper()}",
            "report_date":       ts.strftime("%Y-%m-%d"),
            "report_timestamp":  ts.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "incident_type":     random.choice(INCIDENT_TYPES),
            "district":          district,
            "neighbourhood":     neighbourhood,
            "severity":          random.choice(SEVERITIES),
            "status":            status,
            "officers_assigned": random.randint(1, 6),
            "resolution_hours":  round(random.uniform(0.5, 240), 1) if status == "CLOSED" else None,
            "latitude":          round(random.uniform(45.20, 45.55), 6),
            "longitude":         round(random.uniform(-76.00, -75.45), 6),
            "description":       random.choice(DESCRIPTIONS),
        })
    return records

client = bigquery.Client(project=PROJECT_ID)
table_ref = f"{PROJECT_ID}.{DATASET}.{TABLE}"
records = generate(500)
errors = client.insert_rows_json(client.get_table(table_ref), records)
if errors:
    print(f"Errors: {errors}")
else:
    print(f"✅ 500 records loaded into {table_ref}")
