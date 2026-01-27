# app/tools/financial_tool.py

from google.cloud import bigquery
from datetime import datetime, timedelta
import os
import streamlit as st
import json 


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

def parse_period_simple(period_str):
    """
    Robust Date Parser.
    - '2025' -> '2025' (Yearly search)
    - 'Nov 2025', 'November 2025' -> '2025-11' (Monthly search)
    - None -> '2025-11' (Default fallback)
    """
    if not period_str: return "2025-11"
    
    clean_str = period_str.lower().strip()
    
    # 1. Handle Full Year ("2025")
    if clean_str.isdigit() and len(clean_str) == 4:
        return clean_str
        
    # 2. Handle YYYY-MM
    if "-" in clean_str and clean_str[:4].isdigit(): 
        return clean_str[:7]

    # 3. Handle Text Months ("Nov 2025")
    months = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
              "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"}
    
    for mon, num in months.items():
        if mon in clean_str:
            year = "".join(filter(str.isdigit, clean_str))
            if len(year) == 4: return f"{year}-{num}"
            
    return "2025-11" # Default fallback

def get_chart_data(metric_name: str, chart_type: str = "trend", period: str = None, dimension: str = None, filter_location: str = None, granularity: str = "monthly") -> str:
    
    # --- 1. SETUP ---
    clean_period = parse_period_simple(period)
    raw_metric = metric_name.lower().strip()
    
    # --- 2. SMART MAPPING (Keyword Search) ---
    # We look for these keywords INSIDE the user's string.
    mapping = {
        # Daily Metrics
        "transaction": "Transaction_Count", 
        "ticket": "Avg_Ticket_Size",
        "items sold": "Items_Sold",
        "quantity": "Quantity_Sold",
        
        # Monthly Metrics
        "revenue": "Total_Revenue", "sales": "Total_Revenue",
        "food cost": "COGS", "cogs": "COGS", "product cost": "COGS",
        "labor": "SG&A", "payroll": "SG&A",
        "opex": "OPEX", "operating expenses": "OPEX",
        "net profit": "Net_Profit", "profit": "Net_Profit",
        
        # [CRITICAL FIX] HIERARCHY MAPPING
        # These allow the tool to recognize them as Finance Lines, not Products
        "sg&a": "SG&A", "sga": "SG&A",
        "overheads": "Overheads", "utilities": "Overheads", "rental": "Overheads",
        "facilities": "Facilities", "maintenance": "Facilities", "renovation": "Facilities",
        "advertising": "Advertising", "print advertising": "Advertising",
        "assets": "Assets", "kitchen tools": "Assets"
    }
    
    # Find the first matching keyword in the user string
    found_key = next((k for k in mapping if k in raw_metric), None)
    db_metric = mapping[found_key] if found_key else raw_metric
    
    # --- 3. AUTO-ROUTING LOGIC ---
    
    # List of metrics that ONLY exist in the Daily Table
    daily_only_metrics = ["Transaction_Count", "Items_Sold", "Avg_Ticket_Size", "Total_Discounts"]
    # List of metrics that exist in BOTH (Revenue)
    hybrid_metrics = ["Total_Revenue"]

    # FORCE DAILY: If it's a daily-only metric (like Transactions), force Daily mode.
    if db_metric in daily_only_metrics:
        granularity = "daily"

    # DETECT PRODUCT: If we didn't find a map key, AND it's not a known metric -> It's a Product.
    is_product = (not found_key) and (db_metric not in daily_only_metrics) and (db_metric not in hybrid_metrics)
    
    # === ROUTE A: PRODUCT ANALYSIS ===
    if is_product or "product" in raw_metric:
        # Clean Search Term: "Daily Sales of Big Mac" -> "Big Mac"
        search_term = raw_metric.replace("daily", "").replace("sales", "").replace("trend", "").replace("of", "").replace("visualize", "").strip()

        if granularity == "daily":
            table_name = "POS"
            date_col = "DATE(timestamp)" 
            value_col = "quantity" if "quantity" in raw_metric else "subtotal" 
            
            # LIKE '{clean_period}%' allows '2025%' to match '2025-11-01'
            where_clause = f"WHERE 1=1 AND CAST(DATE(timestamp) AS STRING) LIKE '{clean_period}%'"
            if filter_location: where_clause += f" AND LOWER(location) = '{filter_location.lower()}'"
            
            if "product" not in search_term and "mix" not in search_term:
                 where_clause += f" AND LOWER(product_description) LIKE '%{search_term}%'"
            
            query = f"""
                SELECT CAST({date_col} AS STRING) as label, SUM({value_col}) as value
                FROM `{PROJECT_ID}.fpaa_dataset.{table_name}`
                {where_clause}
                GROUP BY 1 ORDER BY 1 ASC
            """
            chart_tag = "trend"

        else: # Monthly Product
            table_name = "Product_Mix_Analysis"
            value_col = "Quantity_Sold" if "quantity" in raw_metric else "Revenue_Generated"
            where_clause = f"WHERE CAST(Month AS STRING) LIKE '{clean_period}%'"
            if filter_location: where_clause += f" AND LOWER(Location) = '{filter_location.lower()}'"
            
            if "product" not in search_term and "mix" not in search_term:
                where_clause += f" AND LOWER(product_description) LIKE '%{search_term}%'"
                query = f"SELECT CAST(Month AS STRING) as label, SUM({value_col}) as value FROM `{PROJECT_ID}.fpaa_dataset.{table_name}` {where_clause} GROUP BY 1 ORDER BY 1"
                chart_tag = "trend"
            else:
                query = f"SELECT product_description as label, SUM({value_col}) as value FROM `{PROJECT_ID}.fpaa_dataset.{table_name}` {where_clause} GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
                chart_tag = "breakdown"

    # === ROUTE B: DAILY STORE METRICS ===
    elif granularity == "daily":
        table_name = "Daily_Sales_Performance"
        date_col = "Sales_Date"
        # Map generic 'Revenue' to 'Total_Revenue' if needed
        metric_col = db_metric if db_metric in daily_only_metrics + hybrid_metrics else "Total_Revenue"

        where_clause = f"WHERE 1=1 AND CAST(Sales_Date AS STRING) LIKE '{clean_period}%'"
        if filter_location: where_clause += f" AND LOWER(Location) = '{filter_location.lower()}'"

        query = f"SELECT CAST({date_col} AS STRING) as label, CAST(SUM({metric_col}) AS FLOAT64) as value FROM `{PROJECT_ID}.fpaa_dataset.{table_name}` {where_clause} GROUP BY 1 ORDER BY 1 ASC"
        chart_tag = "trend"

    # === ROUTE C: STANDARD FINANCIALS (Monthly P&L) ===
    else:
        # [CRITICAL FIX] Trend Context Logic
        # If user asks for "Trend" of "Nov 2025", we must show the WHOLE YEAR (2025)
        # Otherwise we get a single dot on the chart.
        if chart_type == "trend":
            trend_period = clean_period[:4] # Extract Year (e.g. "2025")
            target_month_clause = f"AND CAST(Month AS STRING) LIKE '{trend_period}%'"
        else:
            # For Bar/Pie, stick to the specific month
            target_month_clause = f"AND CAST(Month AS STRING) LIKE '{clean_period}%'"

        loc_clause = f"AND LOWER(Location) = '{filter_location.lower()}'" if filter_location else ""

        if chart_type == "breakdown":
            if db_metric == "Total_Revenue":
                 query = f"SELECT Location as label, SUM(Revenue) as value FROM `{PROJECT_ID}.fpaa_dataset.Master_PnL_Summary` WHERE 1=1 {target_month_clause} {loc_clause} GROUP BY 1 ORDER BY 2 DESC"
            elif db_metric == "OPEX":
                query = f"SELECT Finance_Line as label, SUM(Actual_Amount) as value FROM `{PROJECT_ID}.fpaa_dataset.Budget_Variance_Detail` WHERE LOWER(Finance_Line) NOT IN ('revenue', 'sales', 'cogs', 'food cost', 'labor') {target_month_clause} {loc_clause} GROUP BY 1 ORDER BY 2 DESC"
            else:
                group_col = "Location" if dimension == "location" else "Subtype"
                # Use db_metric (SG&A) to filter by Finance_Line OR Subtype
                query = f"SELECT {group_col} as label, SUM(Actual_Amount) as value FROM `{PROJECT_ID}.fpaa_dataset.Budget_Variance_Detail` WHERE (LOWER(Finance_Line) = '{db_metric.lower()}' OR LOWER(Subtype) = '{db_metric.lower()}') {target_month_clause} {loc_clause} GROUP BY 1 ORDER BY 2 DESC"
            chart_tag = "breakdown"

        elif chart_type == "budget_vs_actual":
            query = f"SELECT FORMAT_DATE('%b %Y', Month) as label, SUM(Actual_Amount) as actual, SUM(Forecast_Amount) as budget FROM `{PROJECT_ID}.fpaa_dataset.Budget_Variance_Detail` WHERE (LOWER(Finance_Line) = '{db_metric.lower()}' OR LOWER(Subtype) = '{db_metric.lower()}') {target_month_clause} {loc_clause} GROUP BY Month ORDER BY Month ASC"
            chart_tag = "budget_vs_actual"

        else: # Trend
             if not filter_location and db_metric in ["Total_Revenue", "Net_Profit", "OPEX"]:
                 master_col_map = {"Total_Revenue": "Revenue", "Net_Profit": "Net_Profit", "OPEX": "OPEX_Variance"}
                 master_col = master_col_map.get(db_metric, "Revenue")
                 query = f"SELECT CAST(Month AS STRING) as label, CAST(SUM({master_col}) AS FLOAT64) as value FROM `{PROJECT_ID}.fpaa_dataset.Master_PnL_Summary` WHERE 1=1 {target_month_clause} GROUP BY 1 ORDER BY 1"
             else:
                query = f"SELECT CAST(Month AS STRING) as label, CAST(SUM(Actual_Amount) AS FLOAT64) as value FROM `{PROJECT_ID}.fpaa_dataset.Budget_Variance_Detail` WHERE (LOWER(Finance_Line) = '{db_metric.lower()}' OR LOWER(Subtype) = '{db_metric.lower()}') {loc_clause} {target_month_clause} GROUP BY 1 ORDER BY 1"
             chart_tag = "trend"

    # --- 4. EXECUTE ---
    print(f"\n[DEBUG] Request: '{metric_name}' | DB_Metric: '{db_metric}' | Granularity: '{granularity}' | Period: '{clean_period}'")
    
    try:
        df = client.query(query).to_dataframe()
        if not df.empty:
            json_data = df.to_json(orient='records')
            return f"SUCCESS. You MUST output this EXACT tag: <<<CHART_DATA: {chart_tag} | {json_data} >>>"
        else:
            return f"WARNING: No data found for '{metric_name}' during '{clean_period}'. (DB Map: {db_metric})"
    except Exception as e:
        return f"Error fetching chart data: {str(e)}"