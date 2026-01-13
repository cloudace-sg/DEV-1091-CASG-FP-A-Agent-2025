# app/constants.py

# ==============================================================================
# 1. DATA SCHEMA DEFINITIONS
# ==============================================================================
# (Manually Curated: 2025-12-29)
SCHEMA_INFO = """
--- HIGH-LEVEL VIEWS (PRIORITY: USE THESE FIRST) ---

1. VIEW: `fpaa_dataset.Master_PnL_Summary`
   - Use for: Executive summaries of Profit, Revenue, and Cost performance.
   - Columns: Month, Location, Revenue, Net_Profit, COGS_Variance, OPEX_Variance

2. VIEW: `fpaa_dataset.Budget_Variance_Detail`
   - Use for: Investigating specific variances against the plan.
   - Columns: Month, Location, Finance_Line, Subtype, Actual_Amount, Variance_Amount
   - Key Mapping for 'Subtype' Column:
     * "Labour" -> query as 'Payroll'
     * "Maintenance", "Print Advertising", "Renovation", "Rental", "Kitchen tools", "Utilities"

3. VIEW: `fpaa_dataset.Product_Mix_Analysis`
   - Use for: Understanding sales drivers by product.
   - Columns: Month, Location, product_description, Quantity_Sold, Revenue_Generated

4. VIEW: `fpaa_dataset.Daily_Sales_Performance`
   - Use for: Checking daily trends.
   - Columns: Sales_Date, Day_Name, Location, Total_Revenue, Transaction_Count

--- RAW TABLES (USE ONLY IF VIEWS FAIL) ---

5. TABLE: `fpaa_dataset.POS` (Raw Transactions)
   - Columns: product_sku, product_description, quantity, unit_price, month_period, location, discount, subtotal

6. TABLE: `fpaa_dataset.Expenses` (Raw Costs)
   - Columns: scenario, expense_date, location, month_period, finance_line, finance_line_subtype, expense_amount
   - Note: 'scenario' column always = 'Actual'
   - finance_line and finance_line_subtype are related, one finance_line can have many subtypes. Their values are as follows (finance_line: finance_line_subtype): (assets:kitchen tools), (advertising: print advertising), (COGS: product cost), (facilities: maintenance, renovation), (overheads: rental, utilities), (sg&a: payroll, advertising)

7. TABLE: `fpaa_dataset.Forecast` (Budget Forecast)
   - Columns: scenario, forecast_date, location, month_period, finance_line, finance_line_subtype, forecast_amount
   - Note: 'scenario' column always = 'Forecast'
"""

# ==============================================================================
# 2. CENTRALIZED BUSINESS GLOSSARY (Safe for ALL Agents)
# ==============================================================================
BUSINESS_GLOSSARY = """
--- TERM MAPPING ---
- **Spend / Burn**: Refers to 'Expenses' or 'OPEX'.
- **Top Line**: Refers to 'Revenue'.
- **Bottom Line**: Refers to 'Net_Profit'.
- **Stores / Doors**: Refers to 'Location'.
- **PAX**: Refers to 'Transaction_Count' (Customer Traffic).
- **Labour**: Refers to 'Payroll' in finance_line_subtype.
- **Red / Underwater**: 
    - For Revenue: Negative Variance (Actual < Budget) is BAD.
    - For Expenses: Positive Variance (Actual > Budget) is BAD.
- **Food Cost:** The primary Cost of Goods Sold (COGS). When querying, filter by Finance_Line='COGS'.

--- EXPENSE & FORECAST HIERARCHY ---
Use this to identify Finance Lines vs Subtypes.
1. **Assets**: includes `Kitchen tools`
2. **Advertising**: includes `Print advertising`
3. **COGS**: includes `Product cost`, `Food Cost`
4. **Facilities**: includes `Maintenance`, `Renovation`
5. **Overheads**: includes `Rental`, `Utilities`
6. **SG&A**: includes `Payroll`, `Advertising`
"""

# ==============================================================================
# 2. METRICS-SPECIFIC ADD-ONS (SQL Logic)
# ==============================================================================
# ONLY give this to the Metrics Agent.
METRICS_SQL_LOGIC = """
--- CALCULATION RULES (For SQL Fallback) ---
- **Gross Margin**: There is no 'Gross_Margin' column. You MUST calculate it as: `(Revenue - Cost)`.
- **Month-over-Month (MoM)**: When writing SQL, use `LAG()` window functions to compare rows.
"""