from google import genai
from google.cloud import bigquery
from datetime import datetime
import os

PROJECT_ID = "ottawa-police-496223"
client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
bq = bigquery.Client(project=PROJECT_ID)

SCHEMA = """
BigQuery project: ottawa-police-496223, dataset: ops_intelligence
Tables/views:
- incidents: incident_id, report_date, incident_type, district, neighbourhood, severity (LOW/MEDIUM/HIGH/CRITICAL), status (OPEN/UNDER_INVESTIGATION/CLOSED), officers_assigned, resolution_hours
- v_incidents_by_district: district, total_incidents, high_severity_count, open_cases, closed_cases, avg_resolution_hours, clearance_rate_pct (last 30 days)
- v_daily_trend: report_date, daily_total, theft_count, assault_count, vandalism_count, critical_count
- v_open_priority_cases: open HIGH/CRITICAL cases with hours_open, district, neighbourhood, incident_type

Districts: Central, East, West, South, North, Rideau-Rockcliffe
Return ONLY valid standard SQL. No markdown. No explanation.
Always use: `ottawa-police-496223.ops_intelligence.table_name`
"""

def ask(question):
    print(f"\n{'='*60}\n  ANALYST: {question}\n{'='*60}")
    sql = client.models.generate_content(
        model="gemini-2.5-flash-lite",
        contents=f"{SCHEMA}\nWrite SQL to answer: {question}"
    ).text.strip().replace("```sql","").replace("```","").strip()
    print(f"\nSQL Generated:\n{sql}\n")
    try:
        rows = list(bq.query(sql).result())
        if not rows:
            print("AGENT: No data found.")
            return
        rows_text = "\n".join([str(dict(r)) for r in rows[:15]])
        answer = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=f"""You are an AI analyst for Ottawa Police Service.
Question: {question}
Data: {rows_text}
Write a concise operational briefing in plain English under 80 words.
Flag anything urgent. Use specific numbers from the data."""
        ).text.strip()
        print(f"AGENT:\n{answer}")
    except Exception as e:
        print(f"Query error: {e}")
    print('='*60)

print(f"\nOTTAWA POLICE SERVICE — Incident Intelligence Agent")
print(f"Powered by Gemini + BigQuery | {datetime.now().strftime('%Y-%m-%d %H:%M')}")

ask("Show me incident counts by district for the last 30 days")
ask("Which district has the most open high priority cases right now?")
ask("Are there any unusual spikes in incident volume in the last 7 days?")

# Run Q3 with reliable hardcoded SQL
print(f"\n{'='*60}\n  ANALYST: Are there any unusual spikes in incident volume in the last 7 days?\n{'='*60}")
rows = list(bq.query("""
  SELECT district,
    SUM(CASE WHEN report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 7 DAY) THEN 1 ELSE 0 END) AS last_7_days,
    ROUND(SUM(CASE WHEN report_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY) THEN 1 ELSE 0 END) / 4.3, 1) AS expected_weekly_avg
  FROM `ottawa-police-496223.ops_intelligence.incidents`
  GROUP BY district ORDER BY last_7_days DESC
""").result())
rows_text = "\n".join([str(dict(r)) for r in rows])
answer = client.models.generate_content(
    model="gemini-2.5-flash-lite",
    contents=f"""You are an AI analyst for Ottawa Police Service.
Question: Are there any unusual spikes in incident volume in the last 7 days?
Data: {rows_text}
Compare last_7_days vs expected_weekly_avg for each district.
Flag any district where last_7_days is more than 1.5x the expected. Under 80 words."""
).text.strip()
print(f"\nAGENT:\n{answer}")
print('='*60)
