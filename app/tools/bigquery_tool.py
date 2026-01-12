# app/tools/bigquery_tool.py
import os
import re
import decimal
from google.cloud import bigquery

# --- CONFIG ---
SAFE_PROJECT_ID = "strong-kit-475107-k1"
DATASET_ID = "fpaa_dataset"
LOCATION = "asia-southeast1"

# Initialize Client
bq_client = bigquery.Client(project=SAFE_PROJECT_ID, location=LOCATION)
dataset_ref = bq_client.dataset(DATASET_ID)

def query_bigquery(sql_query: str) -> str:
    """
    Executes a SQL query against the FP&A BigQuery Dataset.
    Includes Self-Correction, Currency Formatting, and Data Boundary Checks.

    ** For investigation agent, follow these instructions below:
    [DANGEROUS / FALLBACK ONLY] 
    Executes raw SQL. Use this ONLY for 'Phase 4: Root Cause' to find specific SKUs or Transaction IDs.
    
    STRICT PROHIBITIONS:
    - DO NOT use for 'Revenue vs Last Month' (Use: compare_monthly_metric).
    - DO NOT use for 'Why is X down?' (Use: analyze_variance_drivers).
    - DO NOT use for general health checks (Use: scan_business_health).
    
    If you use this for high-level metrics, the query may fail or return inaccurate data.
    """
    print(f"\n[DEBUG] Running SQL: {sql_query}")

    # 1. SAFETY CHECKS (Standard DML Protection)
    forbidden_keywords = ["DROP", "DELETE", "INSERT", "UPDATE", "ALTER", "TRUNCATE", "GRANT"]
    if any(word in sql_query.upper() for word in forbidden_keywords):
        return f"**Executed SQL:**\n```sql\n{sql_query}\n```\n\n❌ SECURITY BLOCK: Read-only access."

    # 2. DATASET SCOPING (Fixed Logic)
    # enforce that the query mentions the dataset OR assumes the default one.
    if "fpaa_dataset" not in sql_query and "FROM " in sql_query.upper():
         # Optional: Allow queries that rely on default_dataset, but warn if completely foreign
         pass 

    try:
        # 3. EXECUTE QUERY
        # We explicitly set default_dataset. 
        # This means `FROM Table` automatically maps to `fpaa_dataset.Table`
        job_config = bigquery.QueryJobConfig(default_dataset=dataset_ref)
        query_job = bq_client.query(sql_query, job_config=job_config)
        rows = list(query_job.result())
        
        # --- SCENARIO A: EMPTY RESULTS (BOUNDARY CHECK) ---
        is_empty = not rows
        if len(rows) == 1 and all(val is None for val in rows[0].values()):
            is_empty = True

        if is_empty:
            print("[DEBUG] Query result is empty. Starting Boundary Check...")
            
            # Extract table name safely
            match = re.search(r"FROM\s+(?:[`]?[a-zA-Z0-9_]+\.[a-zA-Z0-9_]+[`]?\.)?[`]?([a-zA-Z0-9_]+)[`]?", sql_query, re.IGNORECASE)
            hint_msg = "⚠️ **Zero Results Found.**\n"
            
            if match:
                table_name = match.group(1)
                try:
                    # Check Date Range
                    check_sql = f"SELECT MIN(Month), MAX(Month) FROM `{DATASET_ID}.{table_name}`"
                    bounds = list(bq_client.query(check_sql).result())[0]
                    if bounds[0]:
                        hint_msg += f"**Data Context:** `{table_name}` data range: **{bounds[0]}** to **{bounds[1]}**.\n"
                    else:
                         hint_msg += f"**Data Context:** The table `{table_name}` appears to be empty.\n"
                except:
                     # Fallback for tables without 'Month'
                     hint_msg += "Hint: Check your WHERE clause dates.\n"
            
            return f"**Executed SQL:**\n```sql\n{sql_query}\n```\n\n{hint_msg}"

        # --- SCENARIO B: SUCCESS WITH FORMATTING ---
        headers = list(rows[0].keys())
        
        # 1. define keywords for proper formatting
        money_keywords = ["revenue", "profit", "cost", "sales", "amount", "price", "variance", "expense"]
        pct_keywords = ["percent", "pct", "margin", "rate", "ratio"] 

        # 2. identify column types
        money_cols = {h for h in headers if any(k in h.lower() for k in money_keywords)}
        pct_cols = {h for h in headers if any(k in h.lower() for k in pct_keywords)} 

        # Markdown Table Construction
        md_table = "| " + " | ".join(headers) + " |\n"
        md_table += "| " + " | ".join(["---"] * len(headers)) + " |\n"
        
        for row in rows[:20]: 
            formatted_values = []
            for k in headers:
                val = row[k]
                if isinstance(val, (int, float, decimal.Decimal)):
                    # 3. APPLY FORMATTING PRIORITY
                    if k in pct_cols:
                        # Format as Percentage (e.g., 12.5%)
                        val = f"{val:.2f}%"
                    elif k in money_cols and k not in pct_cols:
                        # Format as Money ONLY if it's not a percentage
                        val = f"${val:,.2f}"
                    else:
                        # Standard Number
                        val = f"{val:,}"
                formatted_values.append(str(val))
            md_table += "| " + " | ".join(formatted_values) + " |\n"
        
        if len(rows) > 20:
            md_table += f"\n*(...{len(rows)-20} more rows truncated)*"

        return f"**Executed SQL:**\n```sql\n{sql_query}\n```\n\n{md_table}"
    except Exception as e:
        # --- SCENARIO C: SELF-CORRECTION LOOP ---
        error_message = str(e)
        return (
            f"**Executed SQL:**\n```sql\n{sql_query}\n```\n\n"
            f"❌ **SQL ERROR**\n"
            f"Error: {error_message}\n\n"
            f"**INSTRUCTIONS:**\n"
            f"1. Check the error message above.\n"
            f"2. Check your Schema (column names often differ from user questions).\n"
            f"3. **REWRITE** the SQL and try again."
        )