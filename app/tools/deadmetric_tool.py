import urllib.parse

def get_missing_metric_link(metric_name: str) -> str:
    """
    Call this tool ONLY when the user requests a metric or calculation 
    that does not exist in the database schema.
    """
    # 1. Safely encode the metric name for a URL (handles spaces and special characters)
    safe_metric = urllib.parse.quote(metric_name)
    
    # 2. Paste your real Google Form URL here (replace the entry.12345 with your real ID)
    form_url = (
        f"https://docs.google.com/forms/d/e/1FAIpQLScXLS21F4_jue7-CmmwcpgxuFhl7kxlMOXJTc-lmlnGSAh5sA/viewform?"
        f"usp=pp_url&entry.2046625733={safe_metric}"
    )
    
    # 3. Return the professional fallback message to the agent
    return (
        f"I'm sorry, but I do not have a verified formula for **'{metric_name}'** in the data store. "
        f"To prevent inaccurate calculations, I cannot estimate this.\n\n"
        f"🚀 **[Click here to request this custom metric from the engineering team]({form_url})**"
    )