# app/tools/visualization_tool.py
import io
import datetime
import uuid
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import seaborn as sns
from google.cloud import storage, bigquery
from matplotlib.ticker import FuncFormatter
import google.auth
import google.auth.transport.requests

# CRITICAL: Use 'Agg' backend to prevent crashing on Cloud Run
matplotlib.use('Agg')

# CONFIG
BUCKET_NAME = "fpaa-reports" 
PROJECT_ID = "strong-kit-475107-k1"
client = bigquery.Client()

# ==============================================================================
# 1. HELPER FUNCTIONS
# ==============================================================================
def upload_chart_to_gcs(buffer, filename_prefix="chart"):
    """
    Uploads a PNG buffer to GCS and returns a short-lived Signed URL.
    Environment-Aware: Works locally (key.json) and in Production (ADC).
    """
    # 1. Create secure, unguessable filename with SGT (UTC+8)
    sgt_timezone = datetime.timezone(datetime.timedelta(hours=8))
    timestamp = datetime.datetime.now(sgt_timezone).strftime("%Y%m%d_%H%M%S")
    unique_id = uuid.uuid4().hex[:8]
    blob_name = f"charts/{filename_prefix}_{timestamp}_{unique_id}.png"

    storage_client = storage.Client()
    bucket = storage_client.bucket(BUCKET_NAME)
    blob = bucket.blob(blob_name)
    
    blob.upload_from_file(buffer, content_type='image/png')
    
    # 2. ENVIRONMENT-AWARE SIGNED URL
    credentials, project_id = google.auth.default()
    
    if not hasattr(credentials, 'signer'):
        # Production Flow (Gemini Enterprise / Cloud Run)
        request = google.auth.transport.requests.Request()
        credentials.refresh(request)
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(hours=1),
            method="GET",
            service_account_email=credentials.service_account_email,
            access_token=credentials.token    # <--- CRITICAL FIX FOR PRODUCTION
        )
    else:
        # Local Flow (Cloud Shell with key.json)
        url = blob.generate_signed_url(
            version="v4",
            expiration=datetime.timedelta(hours=1),
            method="GET"
        )
    
    return url
    
def smart_formatter(x, pos):
    """Dynamically chooses between Currency ($M/K) and Standard Number format."""
    if x >= 1e6:
        return f'${x/1e6:.1f}M'
    elif x >= 1000:
        return f'${x/1000:.0f}K'
    else:
        return f'${int(x):,}'

def generate_static_chart(df, chart_type, title="Financial Chart"):
    """
    Universal Chart Drawer handling:
    1. Trends (Line)
    2. Breakdowns (Horizontal Bar)
    3. Comparisons (Grouped Vertical Bar)
    """
    plt.figure(figsize=(7, 3.5)) 
    sns.set_theme(style="whitegrid", font_scale=0.9)
    
    is_money = any(word in title.lower() for word in ['revenue', 'profit', 'cost', 'opex', 'sales', 'budget', 'payroll', 'labor', 'cogs', 'sg&a', 'overheads', 'facilities', 'utilities', 'rental', 'maintenance', 'advertising'])

    # --- TYPE 1: TREND (Line Chart) ---
    if chart_type == "trend":
        # Hourly Logic Check (Look for HH:MM format)
        first_label = str(df['label'].iloc[0])
        is_hourly = len(first_label) == 5 and ":" in first_label

        if not is_hourly:
            try:
                df['label'] = pd.to_datetime(df['label'])
                df = df.sort_values('label')
            except: pass
        else:
            df = df.sort_values('label')

        ax = sns.lineplot(data=df, x='label', y='value', marker='o', 
                          markersize=8, linewidth=3, color="#003366")
        plt.fill_between(df['label'], df['value'], alpha=0.15, color="#003366")
        
        # Axis Formatting
        if is_money:
            ax.yaxis.set_major_formatter(FuncFormatter(smart_formatter))
            plt.ylabel("Value ($)")
        else:
            ax.yaxis.set_major_formatter(FuncFormatter(lambda x, p: format(int(x), ',')))
            plt.ylabel("Quantity (Units)")
        
        if is_hourly:
            ax.set_xticks(range(len(df)))
            ax.set_xticklabels(df['label'])

        # Data Labels
        for x, y in zip(df['label'], df['value']):
            if y > 0: 
                label = f"${y/1000:.0f}K" if is_money and y >= 1000 else f"{int(y):,}"
                plt.text(x, y, label, color='black', ha='center', va='bottom', fontsize=9, fontweight='bold')

    # --- TYPE 2: BREAKDOWN (Horizontal Bar) ---
    # Good for: Product Mix, OPEX Breakdown, Location Performance
    elif chart_type == "breakdown":
        # Sort top 10 for readability
        df = df.sort_values('value', ascending=False).head(10) 
        
        ax = sns.barplot(data=df, x='value', y='label', hue='label', palette="viridis", legend=False)
        
        if is_money:
            ax.xaxis.set_major_formatter(FuncFormatter(smart_formatter))
            plt.xlabel("Total Amount ($)")
        else:
            ax.xaxis.set_major_formatter(FuncFormatter(lambda x, p: format(int(x), ',')))
            plt.xlabel("Total Quantity (Units)")
        
        # Bar Labels
        for container in ax.containers:
            labels = [f"${v/1000:.0f}K" if is_money and v>=1000 else f"{int(v):,}" for v in container.datavalues]
            ax.bar_label(container, labels=labels, padding=3, fontsize=9)

    # --- TYPE 3: BUDGET vs ACTUAL (Grouped Bar) ---
    # Good for: Variance Analysis
    elif chart_type == "budget_vs_actual":
        # Transform data: Wide (Actual, Budget) -> Long (Type, Amount)
        df_melted = df.melt(id_vars='label', value_vars=['actual', 'budget'], 
                            var_name='Type', value_name='Amount')
        
        # Draw Side-by-Side Bars (Actual=Navy, Budget=Amber)
        ax = sns.barplot(data=df_melted, x='label', y='Amount', hue='Type', 
                         palette={"actual": "#003366", "budget": "#FFC107"})
        
        # Axis Formatting
        ax.yaxis.set_major_formatter(FuncFormatter(smart_formatter))
        plt.ylabel("Amount ($)")
        plt.xlabel("") 
        
        # Bar Labels
        for container in ax.containers:
            labels = [f"${v/1000:.0f}K" if v>=1000 else f"${v:,.0f}" for v in container.datavalues]
            ax.bar_label(container, labels=labels, padding=3, fontsize=8)
            
        # Legend Position
        plt.legend(title="", bbox_to_anchor=(1.02, 1), loc='upper left', borderaxespad=0)

    # --- TYPE 4: PIE CHART (Composition) ---
    elif chart_type == "pie":
        # 1. Clean the data
        df = df.sort_values('value', ascending=False)
        df = df[df['value'] > 0] # Pie charts crash if there are negative numbers
        
        # 2. Group tiny slices into "Other" so the chart doesn't look messy
        if len(df) > 7:
            top_df = df.head(6).copy()
            other_val = df.iloc[6:]['value'].sum()
            other_row = pd.DataFrame({'label': ['Other'], 'value': [other_val]})
            df = pd.concat([top_df, other_row], ignore_index=True)
            
        # 3. Resize figure to be a perfect square for a circular pie
        plt.gcf().set_size_inches(5, 5)
        
        # 4. Build Custom Labels (Name + Amount underneath)
        custom_labels = []
        for _, row in df.iterrows():
            val = row['value']
            # Format as $M, $K, or regular number based on the is_money flag
            if is_money:
                val_str = f"${val/1e6:.1f}M" if val >= 1e6 else (f"${val/1000:.0f}K" if val >= 1000 else f"${int(val):,}")
            else:
                val_str = f"{int(val):,}"
            
            # Combine the Label and the Value with a line break (\n)
            custom_labels.append(f"{row['label']}\n{val_str}")
            
        # 5. Draw it
        colors = sns.color_palette("viridis", len(df))
        plt.pie(df['value'], labels=custom_labels, autopct='%1.1f%%', 
                startangle=140, colors=colors, wedgeprops={'edgecolor': 'white', 'linewidth': 2})
    
    # --- STYLING & SAVE ---
    plt.title(title, fontsize=14, fontweight='bold', pad=20)
    if len(df) > 5 or chart_type == "trend":
        plt.xticks(rotation=30, ha='right')
    sns.despine()
    plt.tight_layout()

    buf = io.BytesIO()
    plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
    buf.seek(0)
    plt.close()

    return upload_chart_to_gcs(buf, filename_prefix=chart_type)

def parse_period_simple(period_str):
    """Robust Date Parser."""
    if period_str:
        clean_str = period_str.lower().strip()
        if clean_str.isdigit() and len(clean_str) == 4: return clean_str
        if "-" in clean_str and clean_str[:4].isdigit(): return clean_str[:7]
        months = {"jan": "01", "feb": "02", "mar": "03", "apr": "04", "may": "05", "jun": "06",
                  "jul": "07", "aug": "08", "sep": "09", "oct": "10", "nov": "11", "dec": "12"}
        for mon, num in months.items():
            if mon in clean_str:
                year = "".join(filter(str.isdigit, clean_str))
                if len(year) == 4: return f"{year}-{num}"
    return (datetime.date.today().replace(day=1) - datetime.timedelta(days=1)).strftime("%Y-%m")

# ==============================================================================
# 2. THE TOOL MAIN FUNCTION
# ==============================================================================
def get_chart_data(metric_name: str, chart_type: str = "trend", period: str = None, dimension: str = None, filter_location: str = None, granularity: str = "monthly") -> str:
    """Generates a financial chart and returns a Markdown image link."""
    
    # --- 1. SETUP ---
    # Fix: Keep full date if provided (YYYY-MM-DD)
    if period and len(period.strip()) == 10:
        clean_period = period.strip()
    else:
        clean_period = parse_period_simple(period)

    # CRITICAL FIX: Handle "Nov 2025" (monthly) vs "Nov 1st" (daily/hourly)
    # If granularity implies a Month view, strip the day
    if granularity in ["daily", "monthly"] and len(clean_period) == 10:
        clean_period = clean_period[:7] 

    raw_metric = metric_name.lower().strip()
    print(f"\n[DEBUG] Request: '{metric_name}' | Period: '{clean_period}' | Granularity: '{granularity}' | Chart: '{chart_type}'")

    # --- 2. SMART MAPPING ---
    # --- 2. SMART MAPPING ---
    mapping = {
        # DAILY / POS METRICS
        "transaction": "Transaction_Count", "ticket": "Avg_Ticket_Size",
        "items sold": "Items_Sold", "quantity": "Quantity_Sold",
        "revenue": "Total_Revenue", "sales": "Total_Revenue",
        "discount": "Total_Discounts", "discounts": "Total_Discounts",
        
        # FINANCE LINES (Map to parent category)
        "cogs": "COGS", "food cost": "COGS", "product cost": "COGS", 
        "sg&a": "SG&A", "sga": "SG&A",
        "opex": "OPEX", "net profit": "Net_Profit", "profit": "Net_Profit",
        "overheads": "Overheads", "facilities": "Facilities", "assets": "Assets",
        
        # SUBTYPES (Map strictly to DB Subtype, No duplicates!)
        "labor": "Payroll", "labour": "Payroll", "payroll": "Payroll", 
        "utilities": "Utilities", "rental": "Rental",
        "maintenance": "Maintenance", "renovation": "Renovation",
        "advertising": "Advertising", "print advertising": "Print advertising"
    }
    found_key = next((k for k in mapping if k in raw_metric), None)
    db_metric = mapping.get(found_key, raw_metric)
    
    daily_only_metrics = ["Transaction_Count", "Items_Sold", "Avg_Ticket_Size", "Total_Discounts"]
    hybrid_metrics = ["Total_Revenue"]

    # Force daily granularity if the metric only exists in daily tables
    if db_metric in daily_only_metrics:
        granularity = "daily"

    # Detect if Product or Financial
    is_product = (not found_key) and (db_metric not in daily_only_metrics) and (db_metric not in hybrid_metrics)
    chart_tag = chart_type 

    # === ROUTE A: PRODUCT ANALYSIS (Includes Product Mix) ===
    if is_product or "product" in raw_metric or "mix" in raw_metric:
        
        # Sub-Route 1: Product Mix (Breakdown of top sellers)
        if chart_type == "breakdown" or "mix" in raw_metric:
             # Use the Aggregated Table for Mix Analysis
             query = f"""
                SELECT product_description as label, SUM(Quantity_Sold) as value
                FROM `fpaa_dataset.Product_Mix_Analysis`
                WHERE CAST(Month AS STRING) LIKE '{clean_period}%'
                GROUP BY 1 ORDER BY 2 DESC LIMIT 10
             """
             chart_tag = "pie" if chart_type == "pie" else "breakdown"
             
        # Sub-Route 2: Trend (Daily/Hourly Sales of a specific product)
        else:
            table_name = "POS"
            date_col = "DATE(timestamp)" 
            if "quantity" in raw_metric:
                value_col = "quantity"
            elif "discount" in raw_metric:
                value_col = "discount"  
            else:
                value_col = "subtotal"
            search_term = raw_metric.replace("daily", "").replace("sales", "").replace("trend", "").strip()
            
            # Check if specific day provided (Drill-down)
            if len(clean_period) > 7:
                date_filter = f"{date_col} = '{clean_period}'"
                current_granularity = "hourly"
            else:
                date_filter = f"CAST({date_col} AS STRING) LIKE '{clean_period}%'"
                current_granularity = "daily"

            if current_granularity == "hourly":
                query = f"SELECT FORMAT_TIMESTAMP('%H:00', timestamp) as label, SUM({value_col}) as value FROM `fpaa_dataset.{table_name}` WHERE {date_filter} AND LOWER(product_description) LIKE '%{search_term}%' GROUP BY 1 ORDER BY 1"
            else:
                query = f"SELECT CAST({date_col} AS STRING) as label, SUM({value_col}) as value FROM `fpaa_dataset.{table_name}` WHERE {date_filter} AND LOWER(product_description) LIKE '%{search_term}%' GROUP BY 1 ORDER BY 1"
            chart_tag = "trend"

    # === ROUTE B: DAILY & HOURLY STORE METRICS ===
    elif granularity in ["daily", "hourly"]:
        table_name = "Daily_Sales_Performance"
        metric_col = db_metric if db_metric in daily_only_metrics + hybrid_metrics else "Total_Revenue"

        is_hourly_request = (granularity == "hourly") or (len(clean_period) == 10)

        if is_hourly_request:
            # Pivot to POS for hourly drill-down
            query = f"""
                SELECT FORMAT_TIMESTAMP('%H:00', timestamp) as label, SUM(subtotal) as value
                FROM `fpaa_dataset.POS`
                WHERE DATE(timestamp) = '{clean_period}'
                {"AND LOWER(location) = '" + filter_location.lower() + "'" if filter_location else ""}
                GROUP BY 1 ORDER BY 1 ASC
            """
            chart_tag = "trend"
        else:
            where_clause = f"WHERE CAST(Sales_Date AS STRING) LIKE '{clean_period}%'"
            if filter_location: where_clause += f" AND LOWER(Location) = '{filter_location.lower()}'"
            query = f"SELECT CAST(Sales_Date AS STRING) as label, SUM({metric_col}) as value FROM `fpaa_dataset.{table_name}` {where_clause} GROUP BY 1 ORDER BY 1 ASC"
            chart_tag = "trend"

    # === ROUTE C: FINANCIALS (Budget vs Actual, P&L) ===
    else:
        # 0. SMART AUTO-CORRECT: Force Pie charts for any location/subtype breakdown
        if dimension in ["location", "subtype"] and chart_type in ["trend", "breakdown"]:
            chart_type = "pie"

        trend_period = clean_period[:4] if chart_type == "trend" else clean_period
        target_month_clause = f"AND CAST(Month AS STRING) LIKE '{trend_period}%'"
        loc_clause = f"AND LOWER(Location) = '{filter_location.lower()}'" if filter_location else ""

        # 1. Budget vs Actual Comparison
        if chart_type == "budget_vs_actual":
            query = f"""
                SELECT FORMAT_DATE('%b %Y', Month) as label, 
                       SUM(Actual_Amount) as actual, 
                       SUM(Forecast_Amount) as budget 
                FROM `fpaa_dataset.Budget_Variance_Detail` 
                WHERE (LOWER(Finance_Line) = '{db_metric.lower()}' OR LOWER(Subtype) = '{db_metric.lower()}') 
                {target_month_clause} {loc_clause} 
                GROUP BY Month ORDER BY Month
            """
            chart_tag = "budget_vs_actual"

        # 2. Breakdown (Pie or Bar)
        elif chart_type in ["breakdown", "pie"]:
            if db_metric == "Total_Revenue":
                 query = f"SELECT Location as label, SUM(Revenue) as value FROM `fpaa_dataset.Master_PnL_Summary` WHERE 1=1 {target_month_clause} {loc_clause} GROUP BY 1 ORDER BY 2 DESC"
            else:
                group_col = "Location" if dimension == "location" else "Subtype"
                filter_logic = f"LOWER(Finance_Line) NOT IN ('revenue', 'sales', 'cogs', 'food cost', 'labor')" if db_metric == "OPEX" else f"(LOWER(Finance_Line) = '{db_metric.lower()}' OR LOWER(Subtype) = '{db_metric.lower()}')"
                
                query = f"""
                    SELECT {group_col} as label, SUM(Actual_Amount) as value 
                    FROM `fpaa_dataset.Budget_Variance_Detail` 
                    WHERE {filter_logic} {target_month_clause} {loc_clause} 
                    GROUP BY 1 ORDER BY 2 DESC
                """
            # Use the requested tag (defaults to pie if auto-corrected)
            chart_tag = "pie" if chart_type == "pie" else "breakdown"
        
        # 3. Trend (RESTORED MISSING LOGIC)
        else:
            if db_metric in ["Total_Revenue", "Net_Profit", "OPEX"] and not filter_location:
                master_col = {"Total_Revenue": "Revenue", "Net_Profit": "Net_Profit", "OPEX": "OPEX_Actual"}.get(db_metric, "Revenue")
                query = f"SELECT CAST(Month AS STRING) as label, SUM({master_col}) as value FROM `fpaa_dataset.Master_PnL_Summary` WHERE CAST(Month AS STRING) LIKE '{trend_period}%' GROUP BY 1 ORDER BY 1"
            else:
                # This was the missing line that caused the $2.2M burger bug!
                query = f"SELECT CAST(Month AS STRING) as label, SUM(Actual_Amount) as value FROM `fpaa_dataset.Budget_Variance_Detail` WHERE (LOWER(Finance_Line) = '{db_metric.lower()}' OR LOWER(Subtype) = '{db_metric.lower()}') {loc_clause} {target_month_clause} GROUP BY 1 ORDER BY 1"
            chart_tag = "trend"


    # --- 4. EXECUTE ---
    try:
        df = client.query(query).to_dataframe()
        if df.empty: return f"WARNING: No data found for '{metric_name}' in '{clean_period}'."

        print(f"\n[DEBUG] Request: '{metric_name}' -> Mapped DB_Metric: '{db_metric}' | Chart: '{chart_tag}'")
        print(f"[DEBUG] Executing SQL:\n{query}")

        chart_url = generate_static_chart(df, chart_tag, title=f"{metric_name} ({clean_period})")
        
        # return f"Chart Generated. Display this link exactly: \n\n![{metric_name} Chart]({chart_url})"
        # Force a clickable text link and prevent the LLM from rendering an image
        '''
        return (
            f"✅ **Chart Generated Successfully!** \n\n"
            f"Here is your secure link to view the chart: **[📊 Click Here to View {metric_name} Chart]({chart_url})** \n\n"
            f"*(Note: For security, this link expires in 1 hour.)*\n\n"
            f"SYSTEM INSTRUCTION TO AGENT: You MUST present this exactly as a text link. DO NOT use the `![alt](url)` image markdown syntax."
        )
        '''
        return f"SUCCESS. The chart has been generated. RAW URL: {chart_url}"

    except Exception as e:
        return f"Error visualizing data: {str(e)}"