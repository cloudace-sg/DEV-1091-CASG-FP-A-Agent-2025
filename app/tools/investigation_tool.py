# app/tools/investigation_tool.py

from google.cloud import bigquery
from typing import Optional
from datetime import datetime, timedelta

# --- CONFIGURATION ---
PROJECT_ID = "strong-kit-475107-k1"
LOCATION = "asia-southeast1"

client = bigquery.Client(project=PROJECT_ID, location=LOCATION)

def analyze_variance_drivers(
    month: str, 
    finance_line: str = None, 
    location_filter: str = None, 
    dimension: str = 'Location'
) -> str:
    """
    [MANDATORY TOOL] Identifies top contributors to a change.
    
    Args:
        month (str): YYYY-MM-DD
        finance_line (str): 
            - For Expenses: Use valid lines: 'COGS', 'SG&A', 'Facilities', 'Overheads', 'Advertising', 'Assets'.
            - For Revenue: Use the special keyword 'Revenue'.
        location_filter (str): Optional filter (e.g., 'MCD_1').
        dimension (str): 'Location' or 'Subtype'.
    """
    
    # --- PATH A: REVENUE ANALYSIS ---
    # Revenue is NOT a finance_line in the DB, so handled seperately
    if finance_line and finance_line.lower() in ['revenue', 'sales', 'total_revenue']:
        return _analyze_revenue_drivers(month, location_filter, dimension)

    # --- PATH B: EXPENSE ANALYSIS ---
    # strictly queries 'Budget_Variance_Detail' view using finance_line
    
    valid_dims = {'Location', 'Subtype', 'Finance_Line'}
    if dimension not in valid_dims:
        return f"Error: Dimension '{dimension}' is not valid."

    conditions = [f"Month = '{month}'"]
    
    # Only apply finance_line filter if it's a valid expense
    if finance_line:
        conditions.append(f"Finance_Line = '{finance_line}'")
        
    if location_filter:
        conditions.append(f"Location = '{location_filter}'")
    
    where_clause = " WHERE " + " AND ".join(conditions)

    sql = f"""
        SELECT 
            {dimension}, 
            SUM(Actual_Amount) as Actual, 
            SUM(Variance_Amount) as Variance
        FROM `{PROJECT_ID}.fpaa_dataset.Budget_Variance_Detail`
        {where_clause}
        GROUP BY {dimension}
        ORDER BY ABS(Variance) DESC
        LIMIT 5
    """
    # --- DEBUG PRINT for SQL Statement ---
    print(f"\n[DEBUG] analyze_variance_drivers SQL:\n{sql}\n") 
    # ------------------------------

    try:
        # avoids pandas/db-dtypes dependency
        results = list(client.query(sql).result())
        
        if not results:
            return (f"No variance found for {finance_line or 'all expenses'} in {month}. "
                    "Check if the finance_line is valid (COGS, SG&A, Facilities, Overheads, Advertising, Assets).")

        output = [f"**Variance Analysis ({dimension})**"]
        for row in results:
            variance = row.Variance or 0.0
            actual = row.Actual or 0.0
            # For Expenses: Positive Variance = Bad (Over Budget)
            status = "Over Budget" if variance > 0 else "Under Budget"
            name = getattr(row, dimension, "Unknown")
            output.append(f"- **{name}**: {status} by ${abs(variance):,.0f} (Actual: ${actual:,.0f})")

        # --- instructions to stop looping ---
        if dimension == 'Location':
            output.append("\nNOTE TO AGENT: You have identified the Location drivers. "
                          "Next Step: Call `analyze_variance_drivers(dimension='Subtype')` "
                          "for the top location to find the specific expense category.")
        elif dimension == 'Subtype':
            output.append("\nNOTE TO AGENT: You have identified the Expense Category. "
                          "Investigation is complete. "
                          "Please report these findings to the user. DO NOT run this tool again.")   
                           
        return "\n".join(output)

    except Exception as e:
        return f"Error analyzing expense drivers: {str(e)}"

def _analyze_revenue_drivers(current_month: str, location_filter: str, dimension: str):
    """
    Helper to analyze Revenue. Since Revenue is not in the Expense table,
    we query 'Product_Mix_Analysis' instead.
    """
    # calculate Previous Month
    try:
        curr_date = datetime.strptime(current_month, "%Y-%m-%d")
        prev_date = (curr_date.replace(day=1) - timedelta(days=1)).replace(day=1)
        previous_month = prev_date.strftime("%Y-%m-%d")
    except ValueError:
        return f"Error: Date format must be YYYY-MM-DD (got {current_month})"

    # map dims to revenue table
    # revenue table uses 'product_description', not 'Subtype'
    col_map = {
        'Location': 'Location',
        'Subtype': 'product_description' 
    }
    target_col = col_map.get(dimension, 'Location')

    where_sql = f"AND Location = '{location_filter}'" if location_filter else ""

    sql = f"""
        SELECT 
            {target_col} as Name,
            SUM(CASE WHEN Month = '{current_month}' THEN Revenue_Generated ELSE 0 END) as Curr,
            SUM(CASE WHEN Month = '{previous_month}' THEN Revenue_Generated ELSE 0 END) as Prev
        FROM `{PROJECT_ID}.fpaa_dataset.Product_Mix_Analysis`
        WHERE Month IN ('{current_month}', '{previous_month}')
        {where_sql}
        GROUP BY 1
        HAVING Curr <> Prev
        ORDER BY ABS(Curr - Prev) DESC
        LIMIT 5
    """

    # --- DEBUG PRINT for SQL Statement ---
    print(f"\n[DEBUG] _analyze_revenue_drivers SQL:\n{sql}\n") 
    # ------------------------------
    
    try:
        results = list(client.query(sql).result())
        if not results: return "No significant revenue changes found."
        
        output = [f"**Revenue Drivers ({dimension})**"]
        for row in results:
            delta = row.Curr - row.Prev
            direction = "Increased" if delta > 0 else "Decreased"
            output.append(f"- **{row.Name}**: {direction} by ${abs(delta):,.0f} (Current: ${row.Curr:,.0f})")

        return "\n".join(output)
    except Exception as e:
        return f"Error analyzing revenue: {str(e)}"

def compare_monthly_metric(current_month: str, previous_month: str, metric_name: str) -> str:
    """
    Compares a specific metric (Revenue, Net_Profit, COGS_Variance) between two months.
    Requires arguments from 2 months
    """
    # safety whitelist to guardrail
    allowed_metrics = {'Revenue', 'Net_Profit', 'COGS_Variance', 'OPEX_Variance', 'Total_Revenue'}
    
    if metric_name not in allowed_metrics:
         return f"Error: Metric '{metric_name}' is not supported."
    
    # handle the 'Total_Revenue' alias if the agent uses it
    actual_col = 'Revenue' if metric_name == 'Total_Revenue' else metric_name
         
    sql = f"""
        SELECT Month, SUM({actual_col}) as Value 
        FROM `{PROJECT_ID}.fpaa_dataset.Master_PnL_Summary`
        WHERE Month IN ('{current_month}', '{previous_month}')
        GROUP BY Month ORDER BY Month
    """

    # --- DEBUG PRINT for SQL Statement ---
    print(f"\n[DEBUG] compare_monthly_metric SQL:\n{sql}\n") 
    # ------------------------------
    
    try:
        # avoids pandas/db-dtypes dependency
        query_job = client.query(sql)
        results = list(query_job.result())
        
        if len(results) < 2:
            return f"Insufficient data. Found {len(results)} months, need 2 to compare."
            
        # results are ordered by Month
        # index 0 is previous, 1 is current
        prev_row = results[0]
        curr_row = results[1]
        
        prev_val = prev_row.Value or 0.0
        curr_val = curr_row.Value or 0.0
        
        delta = curr_val - prev_val
        pct_change = (delta / prev_val) * 100 if prev_val != 0 else 0.0
        
        direction = "INCREASED" if delta > 0 else "DECREASED"
        
        return (
            f"**{metric_name} MoM Comparison:**\n"
            f"- {prev_row.Month}: ${prev_val:,.0f}\n"
            f"- {curr_row.Month}: ${curr_val:,.0f}\n"
            f"- Result: {direction} by ${abs(delta):,.0f} ({pct_change:.1f}%)\n\n"
            f"NOTE TO AGENT: The user asked 'Why'. "
            f"You have confirmed the variance. "
            f"NOW you MUST call `analyze_variance_drivers(dimension='Location')` to find the driver."
        )

    except Exception as e:
        return f"Error comparing months: {str(e)}"

def scan_business_health(month: str) -> str:
    """
    Proactively scans all locations to identify 'Risks' (Over Budget) 
    and 'Top Performers' (Under Budget) for the given month.
    """
    sql = f"""
        SELECT Location, SUM(Actual_Amount) as Actual, SUM(Variance_Amount) as Variance
        FROM `{PROJECT_ID}.fpaa_dataset.Budget_Variance_Detail`
        WHERE Month = '{month}'
        GROUP BY Location
        ORDER BY Variance DESC
    """

    # --- DEBUG PRINT for SQL Statement ---
    print(f"\n[DEBUG] scan_business_health SQL:\n{sql}\n") 
    # ------------------------------

    try:
        # avoids pandas/db-dtypes dependency
        results = list(client.query(sql).result())
        
        if not results: 
            return f"No data found for {month}."

        # Logic: 
        # results are ordered DESC (Highest Positive first)
        # Positive Variance = Over Budget (Risk)
        # Negative Variance = Under Budget (Savings)
        
        risks = results[:2]   # Take top 2 stores
        performers = results[-2:] # Take bottom 2 stores
        
        # Handle small lists (if fewer than 4 items total)
        if len(results) < 2:
            performers = []

        report = [f"** 🏥 Business Health Scan ({month}) **\n"]
        
        report.append("🚩 **Risk Areas (Over Budget):**")
        for row in risks:
            var = row.Variance or 0.0
            act = row.Actual or 0.0
            if var > 0:
                report.append(f"- **{row.Location}**: Over by ${var:,.0f} (Total Spend: ${act:,.0f})")
            else:
                report.append("- (None detected)")
            
        report.append("\n🚀 **Top Performers (Under Budget):**")
        # reverse performers so the "best" (most negative) is shown first or list all.
        for row in performers:
            var = row.Variance or 0.0
            if var < 0:
                report.append(f"- **{row.Location}**: Saved ${abs(var):,.0f}")
                
        return "\n".join(report)

    except Exception as e:
        return f"Error scanning health: {str(e)}"

def detect_anomalies(month: str, table_type: str = 'Expenses') -> str:
    """
    [MANDATORY TOOL] for "Anomaly", "Data Error", or "Spike" questions.
    Scans for single-transaction outliers (> 3x the category average).
    
    Args:
        month (str): YYYY-MM-DD
        table_type (str): 'Expenses' (default) or 'Revenue'.
    """
    # map names to actual BQ tables and columns
    table_map = {
        'Expenses': {'name': 'fpaa_dataset.Expenses', 'col': 'expense_amount', 'cat': 'finance_line_subtype'},
        'Revenue': {'name': 'fpaa_dataset.POS', 'col': 'subtotal', 'cat': 'product_description'}
    }
    
    config = table_map.get(table_type)
    if not config: 
        return "Error: Invalid table_type. Choose 'Expenses' or 'Revenue'."

    # SQL Strategy:
    # 1. Calculate Average per Category (CTE 'Stats')
    # 2. Join back to find individual rows > 3x that Average
    sql = f"""
        WITH Stats AS (
            SELECT {config['cat']} as Cat, AVG({config['col']}) as AvgVal
            FROM `{PROJECT_ID}.{config['name']}`
            WHERE month_period = '{month}'
            GROUP BY 1
        )
        SELECT 
            t.location, 
            t.{config['cat']} as Item, 
            t.{config['col']} as Amount, 
            s.AvgVal
        FROM `{PROJECT_ID}.{config['name']}` t
        JOIN Stats s ON t.{config['cat']} = s.Cat
        WHERE t.month_period = '{month}'
        AND t.{config['col']} > (s.AvgVal * 3) -- The "3x" Outlier Rule
        ORDER BY t.{config['col']} DESC
        LIMIT 5
    """
    
    # --- DEBUG PRINT for SQL Statement ---
    print(f"\n[DEBUG] detect_anomalies SQL:\n{sql}\n") 
    # ------------------------------

    try:
        # avoids pandas/db-dtypes dependency
        results = list(client.query(sql).result())
        
        if not results: 
            return f"No anomalies detected (no single transaction > 3x average) in {month} for {table_type}."
        
        output = [f"**🚨 Potential Anomalies ({table_type}) in {month}**"]
        for row in results:
            avg_val = row.AvgVal or 1.0 # Avoid division by zero
            multiple = row.Amount / avg_val
            output.append(f"- **{row.location}**: Found a {row.Item} transaction of **${row.Amount:,.0f}** "
                          f"(Normal avg: ${row.AvgVal:,.0f} -> {multiple:.1f}x higher)")
        
        return "\n".join(output)
    except Exception as e:
        return f"Error detecting anomalies: {str(e)}"