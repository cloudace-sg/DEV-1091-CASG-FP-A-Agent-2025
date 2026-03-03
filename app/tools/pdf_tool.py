import io
import uuid
from datetime import datetime, timezone, timedelta
import markdown
import re
import requests
import base64
from xhtml2pdf import pisa
from google.cloud import storage
import google.auth
import google.auth.transport.requests

# CONFIG
BUCKET_NAME = "fpaa-reports"

def export_to_pdf(report_markdown: str) -> str:
    """
    Converts a Markdown report to a PDF, pre-fetches any secure images, 
    uploads it securely, and returns a URL.
    Environment-Aware: Works locally (key.json) and in Production (ADC).
    """
    if not report_markdown or len(report_markdown.strip()) < 20:
        return "ERROR: The provided report content is empty. Please ask the user to generate a full report first."

    try:
        # --- NEW FIX: Unescape literal newlines from the JSON payload ---
        report_markdown = report_markdown.replace('\\n', '\n')
        
        report_markdown = re.sub(r'\\+\$', '$', report_markdown) 
        report_markdown = report_markdown.replace("\\'", "'")  
        report_markdown = report_markdown.replace('\\"', '"')

        # 1. Convert Markdown to HTML
        html_body = markdown.markdown(report_markdown, extensions=['tables', 'fenced_code'])

        # === PRE-FETCH & EMBED IMAGES FROM HYPERLINKS (MAGIC PDF FIX) ===
        def fetch_link_and_convert_to_image(match):
            original_text = match.group(0)
            img_url = match.group(1).replace("&amp;", "&") 
            
            # Look for our new clean Cloud Run proxy URL
            if "/charts/" in img_url:
                try:
                    # =========================================================
                    # FIX: The Python Air-Gap Bypass
                    # Extract just the filename from the end of the URL
                    # e.g., "budget_vs_actual_123.png"
                    filename = img_url.split('/')[-1]
                    blob_name = f"charts/{filename}"
                    
                    # Use Python SDK to download image natively from the private bucket
                    storage_client = storage.Client()
                    bucket = storage_client.bucket(BUCKET_NAME)
                    blob = bucket.blob(blob_name)
                    
                    image_bytes = blob.download_as_bytes()
                    img_base64 = base64.b64encode(image_bytes).decode('utf-8')
                    
                    # Return ONLY the image to the PDF renderer. 
                    return f'<br><img src="data:image/png;base64,{img_base64}"><br>'
                        
                except Exception as e:
                    print(f"[DEBUG] Base64 Image Bypass Error: {str(e)}")
            
            # If it fails, leave the original text intact
            return original_text

        # NEW REGEX: Safely target ONLY the "Click here..." sentence and grab the new short URL.
        html_body = re.sub(
            r'<p>[^<]*Click here[^<]*</p>\s*<pre><code[^>]*>\s*(https://[^\s<]+/charts/[^\s<]+)\s*</code></pre>', 
            fetch_link_and_convert_to_image, 
            html_body, 
            flags=re.IGNORECASE
        )
        # ================================================================
        # ================================================================

        # === GET LOCAL SGT TIME ===
        sgt_timezone = timezone(timedelta(hours=8))
        local_time_now = datetime.now(sgt_timezone)
        local_time_str = local_time_now.strftime("%Y-%m-%d %H:%M")
        # ==========================

        # 2. Add Corporate Styling
        html_content = f"""
        <html>
        <head>
            <style>
                @page {{ 
                    size: A4; 
                    margin: 1.5cm; 
                    @frame footer {{
                        -pdf-frame-content: footer_content;
                        bottom: 1cm;
                        margin-left: 1.5cm;
                        margin-right: 1.5cm;
                        height: 1cm;
                    }}
                }}
                body {{ font-family: Helvetica, Arial, sans-serif; font-size: 12px; color: #333; line-height: 1.5; }}
                h1 {{ color: #003366; border-bottom: 2px solid #003366; padding-bottom: 5px; font-size: 18px; }}
                h2, h3, h4 {{ color: #003366; margin-top: 15px; margin-bottom: 5px; }}
                table {{ width: 100%; border-collapse: collapse; margin-bottom: 20px; table-layout: fixed; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; word-wrap: break-word; overflow-wrap: break-word; }}
                th {{ background-color: #f2f2f2; color: #003366; font-weight: bold; }}
                img {{ width: 600px; display: block; margin: 15px auto; }}
                .footer-text {{ font-size: 9px; text-align: center; color: #777; }}
            </style>
        </head>
        <body>
            <h1>Financial Performance Report</h1>
            <p><em>Generated on: {local_time_str} (SGT)</em></p>
            <hr>
            {html_body}
            <div id="footer_content" class="footer-text">
                Generated securely by CASG FPAA AI Assistant | Strictly Private & Confidential
            </div>
        </body>
        </html>
        """

        # 3. Create PDF in memory
        pdf_buffer = io.BytesIO()
        pisa_status = pisa.CreatePDF(io.StringIO(html_content), dest=pdf_buffer)
        
        if pisa_status.err:
            return "ERROR: Failed to generate PDF layout."

        pdf_buffer.seek(0)

        # 4. Securely Upload to GCS
        unique_id = uuid.uuid4().hex # <--- Use full UUID for maximum security
        timestamp = local_time_now.strftime("%Y%m%d_%H%M%S")
        filename = f"Financial_Report_{timestamp}_{unique_id}.pdf"
        blob_name = f"pdfs/{filename}"

        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)
        blob.upload_from_file(pdf_buffer, content_type='application/pdf')
        
        # 5. RETURN CLEAN PROXY URL (NO SIGNATURES)
        base_url = "https://fpaa-ge-backend-929980771057.asia-southeast1.run.app" 
        clean_url = f"{base_url}/pdfs/{filename}"

        # We can finally use a beautiful, clickable Markdown link!
        return (
            f"✅ **PDF Generated Successfully!**\n\n"
            f"**[📥 Click Here to Securely Download Your PDF Report]({clean_url})**\n\n"
            f"*(Note: For security, this link expires in 24 hours.)*"
        )
    except Exception as e:
        return f"Error generating PDF: {str(e)}"