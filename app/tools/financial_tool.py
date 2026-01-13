# app/tools/financial_tool.py

from google.cloud import bigquery
from datetime import datetime, timedelta
import os

# --- CONFIGURATION ---
PROJECT_ID = "strong-kit-475107-k1"
LOCATION = "asia-southeast1"

client = bigquery.Client(project=PROJECT_ID, location=LOCATION)

def get_pnl_comparison(metric: str, start_date: str, end_date: str, compare_start_date: str = None) -> str:
    """
    Calculates a specific P&L metric over a time period, optionally comparing it to a previous period.
    """
    
    # 1. Map "User Speak" to "Database Columns"
    # do not include Gross Margin/Cost to force the agent to use SQL for those.
    metric_map = {
        "Revenue": "Revenue",
        "Net_Profit": "Net_Profit",
        "OPEX": "OPEX_Variance", 
    }
    
    db_column = metric_map.get(metric)
    
    if not db_column:
        # Check if valid column passed directly
        valid_columns = ["Revenue", "Net_Profit", "OPEX_Variance", "COGS_Variance"]
        if metric in valid_columns:
            db_column = metric
        else:
            # return instructions to agent to use SQL for questions outside scope
            return f"Error: Metric '{metric}' is not supported by this tool (Try: Revenue, Net_Profit). For 'Gross Margin', please use the SQL tool."

    # 2. Helper to run a safe query
    def get_value(s_date, e_date):
        # use the PROJECT_ID variable in the SQL string
        sql = f"""
            SELECT SUM({db_column}) as val
            FROM `{PROJECT_ID}.fpaa_dataset.Master_PnL_Summary`
            WHERE Month BETWEEN '{s_date}' AND '{e_date}'
        """
        
        # --- DEBUG PRINT for SQL Statement ---
        print(f"\n[DEBUG] get_pnl_comparison SQL:\n{sql}\n") 
        # ------------------------------

        try:
            job = client.query(sql, location=LOCATION)
            result = job.result()
            for row in result:
                # FIX: Force conversion to float to match the default 0.0
                return float(row.val or 0.0) 
            return 0.0
        except Exception as e:
            print(f"[TOOL ERROR] Query Failed: {e}") 
            return 0.0

    # 3. Calculate Current Period
    current_val = get_value(start_date, end_date)

    # 4. Handle Simple Request with start and end date
    if not compare_start_date:
        return f"The total {metric} from {start_date} to {end_date} was ${current_val:,.2f}."

    # 5. Handle Comparison Request
    fmt = "%Y-%m-%d"
    try:
        d1 = datetime.strptime(start_date, fmt)
        d2 = datetime.strptime(end_date, fmt)
        duration = (d2 - d1).days
        
        comp_s = datetime.strptime(compare_start_date, fmt)
        comp_e = comp_s + timedelta(days=duration)
        compare_end_date = comp_e.strftime(fmt)
    except ValueError:
        return "Error: Dates must be in YYYY-MM-DD format."

    previous_val = get_value(compare_start_date, compare_end_date)
    
    # 6. Calculate Variance
    diff = current_val - previous_val
    if previous_val == 0:
        pct_change = 0.0
    else:
        pct_change = (diff / previous_val) * 100

    # 7. Formatting
    direction = "up" if diff >= 0 else "down"
    variance_str = f"${abs(diff):,.2f}"
    variance_sign = "+" if diff >= 0 else "-"
    
    return (
        f"**{metric} Analysis**\n"
        f"Current Period ({start_date} to {end_date}): ${current_val:,.2f}\n"
        f"Prior Period   ({compare_start_date} to {compare_end_date}): ${previous_val:,.2f}\n"
        f"Variance: {variance_sign}{variance_str} ({direction} {pct_change:.1f}%)"
    )

    
def analyze_gross_margin(target_month: str, comparison_month: str = None) -> str:
    """Calculates Gross Margin (mapped to Net_Profit) with MoM comparison."""
    sql = f"""
        SELECT Month, SUM(Net_Profit) as GM_Value
        FROM `{PROJECT_ID}.fpaa_dataset.Master_PnL_Summary`
        WHERE Month = '{target_month}' 
           OR Month = '{comparison_month}'
        GROUP BY Month  -- <--- THIS WAS MISSING
    """
    
    # --- DEBUG PRINT for SQL Statement ---
    print(f"\n[DEBUG] analyze_gross_margin SQL:\n{sql}\n")
    # ------------------------------
    try:
        query_job = client.query(sql, location=LOCATION)
        # We need to format the date key as a string to match the input
        results = {row.Month.strftime("%Y-%m-%d"): row.GM_Value for row in query_job.result()}
    except Exception as e:
        return f"Error querying Gross Margin data: {str(e)}"

    current_gm = results.get(target_month, 0.0)
    prior_gm = results.get(comparison_month, 0.0)

    diff = current_gm - prior_gm
    pct = (diff / prior_gm * 100) if prior_gm != 0 else 0.0
    
    return (
        f"**Gross Margin Analysis (MoM)**\n"
        f"Note: Based on dataset limitations, Gross Margin is derived from Net Profit.\n"
        f"- **{target_month}**: ${current_gm:,.2f}\n"
        f"- **{comparison_month}**: ${prior_gm:,.2f}\n"
        f"- **Variance**: {'+' if diff >=0 else ''}${diff:,.2f} ({pct:+.1f}%)"
    )
    

def get_revenue_variance(start_date: str, end_date: str) -> str:
    """
    Safe handler for Revenue Variance requests. 
    It fetches Actuals and explicitly reports that Budget data is missing.
    """
    # 1. Fetch Actuals
    sql = f"""
        SELECT SUM(Revenue) as Total_Revenue 
        FROM `{PROJECT_ID}.fpaa_dataset.Master_PnL_Summary` 
        WHERE Month BETWEEN '{start_date}' AND '{end_date}'
    """

    # --- DEBUG PRINT for SQL Statement ---
    print(f"\n[DEBUG] get_revenue_variance SQL:\n{sql}\n")
    # ------------------------------
    
    try:
        query_job = client.query(sql, location=LOCATION)
        result = next(query_job.result())
        actual_revenue = result.Total_Revenue or 0.0
    except Exception as e:
        return f"Error querying Actual Revenue: {str(e)}"

    # 2. Return revenue variance analysis (Guardrailed to prevent hallucination)
    # does not return variance as dataset currently does not have total targets
    return (
        f"**Revenue Variance Analysis ({start_date} to {end_date})**\n"
        f"- **Actual Revenue**: ${actual_revenue:,.2f}\n"
        f"- **Budgeted Revenue**: N/A (Data Unavailable in Forecast Table)\n"
        f"- **Variance**: Cannot calculate %.\n\n"
        f"*System Note: The 'Forecast' table tracks Expenses only. Revenue targets are not currently loaded.*"
    )

def get_budget_variance(month: str, finance_line: str = None, subtype: str = None) -> str:
    """
    Retrieves Budget vs Actual variance. Can filter by Finance Line OR specific Subtype.
    """
    
    # 1. Handle Revenue Redirect
    if finance_line and finance_line.lower() in ['revenue', 'sales']:
        return "Error: For Revenue, use the `get_revenue_variance` tool."

    # 2. Build Query Conditions
    conditions = [f"Month = '{month}'"]
    
    if finance_line:
        conditions.append(f"Finance_Line = '{finance_line}'")
    
    # --- NEW: Support Subtype filtering ---
    if subtype:
        # Lowercase match to be safe
        conditions.append(f"LOWER(Subtype) = '{subtype.lower()}'")
    
    where_clause = " AND ".join(conditions)
    
    # 3. Dynamic SQL
    sql = f"""
        SELECT 
            SUM(Actual_Amount) as Actual, 
            SUM(Forecast_Amount) as Budget,
            SUM(Variance_Amount) as Variance
        FROM `{PROJECT_ID}.fpaa_dataset.Budget_Variance_Detail`
        WHERE {where_clause}
    """
    
    # Debug Print
    print(f"\n[DEBUG] get_budget_variance SQL:\n{sql}\n")

    try:
        query_job = client.query(sql)
        # Handle empty results (e.g. if subtype is misspelled)
        results = list(query_job.result())
        if not results:
            return f"No data found for {subtype or finance_line} in {month}."
            
        row = results[0]
        
        if row.Actual is None:
            return f"No data found for {subtype or finance_line} in {month}."

        act = row.Actual or 0.0
        bud = row.Budget or 0.0
        var = row.Variance or 0.0
        
        # 4. Standardized Formatting
        status = "Unfavorable (Over Budget)" if var > 0 else "Favorable (Under Budget)"
        
        return (
            f"**Budget Variance Report ({month})**\n"
            f"- **Item**: {subtype or finance_line or 'Total Expenses'}\n"
            f"- **Actual**: ${act:,.2f}\n"
            f"- **Budget**: ${bud:,.2f}\n"
            f"- **Variance**: ${abs(var):,.2f} {status}"
        )

    except Exception as e:
        return f"Error calculating variance: {str(e)}"