# app/constants.py

# ==============================================================================
# 1. DATA SCHEMA DEFINITIONS
# ==============================================================================
# (Manually Curated: 2025-12-29)
SCHEMA_INFO = """
--- HIGH-LEVEL VIEWS (PRIORITY: USE THESE FIRST) ---

1. VIEW: `fpaa_dataset.Master_PnL_Summary`
   - Use for: Executive summaries of Profit, Revenue, and Cost performance.
   - Columns: Month, Location, Revenue, COGS_Actual, OPEX_Actual, Gross_profit, Operating_Profit, Net_Profit, COGS_Variance, OPEX_Variance

2. VIEW: `fpaa_dataset.Budget_Variance_Detail`
   - Use for: Investigating specific variances against the plan.
   - Columns: Month, Location, Finance_Line, Subtype, Actual_Amount, Forecast_Amount, Variance_Amount, Variance_Percent
   - Key Mapping for 'Subtype' Column:
     * "Labour" -> query as 'Payroll'
     * "Maintenance", "Print Advertising", "Renovation", "Rental", "Kitchen tools", "Utilities"

3. VIEW: `fpaa_dataset.Product_Mix_Analysis`
   - Use for: Understanding sales drivers by product.
   - Columns: Month, Location, product_sku, product_description, Quantity_Sold, Revenue_Generated, Menu_price, Avg_Effective_Price

4. VIEW: `fpaa_dataset.Daily_Sales_Performance`
   - Use for: Checking daily trends.
   - Columns: Sales_Date, Day_Name, Location, Total_Revenue, Transaction_Count, Items_sold, Total_Discounts, Avg_ticket_size, units_per_transaction

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
- **Month-over-Month (MoM)**: When writing SQL, use `LAG()` window functions to compare rows.
- **Contribution Margin (CM%)**: 
  1. Do NOT run multiple queries. You MUST calculate it using a single JOIN query.
     *Example Structure:* `SELECT pnl.Revenue, cost.Actual_Amount as Product_Cost, ((pnl.Revenue - cost.Actual_Amount) / pnl.Revenue) * 100 as CM_Pct FROM fpaa_dataset.Master_PnL_Summary pnl JOIN fpaa_dataset.Budget_Variance_Detail cost ON pnl.Month = cost.Month AND pnl.Location = cost.Location WHERE LOWER(cost.Subtype) = 'product cost'`
  2. You MUST format the final output as a clean, bulleted list showing the math. 
     *Format Template:*
     - **Total Revenue**: \$[Amount]
     - **Product Cost**: \$[Amount]
     - **Contribution Margin (CM%)**: [Percentage]%

"""

# ==============================================================================
# 3. STREAMLIT FORMATTING (Currency)
# ==============================================================================
STREAMLIT_FORMATTING_INSTRUCTIONS = """
### TECHNICAL FORMATTING RULES (CRITICAL):
1. **DO NOT** use LaTeX formatting (no $...$ or $$...$$).
2. When formatting currency, **ALWAYS escape the dollar sign** by putting a backslash before it.
   - WRONG: $10,000
   - WRONG: $ 10,000
   - CORRECT: \$10,000
3. Alternatively, use "SGD" instead of a symbol (e.g., "10,000 SGD").
4. Never wrap sentences or text in dollar signs.
"""