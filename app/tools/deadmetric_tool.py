import urllib.parse

def get_missing_metric_link(metric_name: str, is_custom_calculation: bool = False) -> str:
    """
    Call this tool when a user requests a metric not in the schema, OR 
    after successfully calculating a custom formula provided by the user.
    """
    safe_metric = urllib.parse.quote(metric_name)
    form_url = (
        f"https://docs.google.com/forms/d/e/1FAIpQLScXLS21F4_jue7-CmmwcpgxuFhl7kxlMOXJTc-lmlnGSAh5sA/viewform?"
        f"usp=pp_url&entry.2046625733={safe_metric}"
    )
    
    if is_custom_calculation:
        return (
            f"---\n"
            f"💡 **DISCLAIMER:** This was a custom, unverified calculation based on your prompt. \n\n"
            f"To make **'{metric_name}'** a permanent standard metric in our system:\n\n"
            f"🚀 **[Click here to submit it to the Formula Registry]({form_url})**"
        )
    else:
        return (
            f"I'm sorry, but I do not have a verified formula for **'{metric_name}'** in the data store. "
            f"To prevent inaccurate calculations, I cannot estimate this.\n\n"
            f"\n🚀 **[Click here to request this custom metric from the engineering team]({form_url})**"
        )