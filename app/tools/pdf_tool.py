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
    uploads it securely, and returns a 15-minute Signed URL.
    Environment-Aware: Works locally (key.json) and in Production (ADC).
    """
    if not report_markdown or len(report_markdown.strip()) < 20:
        return "ERROR: The provided report content is empty. Please ask the user to generate a full report first."

    try:
        report_markdown = re.sub(r'\\+\$', '$', report_markdown) 
        report_markdown = report_markdown.replace("\\'", "'")  
        report_markdown = report_markdown.replace('\\"', '"')

        # 1. Convert Markdown to HTML
        html_body = markdown.markdown(report_markdown, extensions=['tables', 'fenced_code'])

        '''
        
        # === PRE-FETCH & EMBED IMAGES ===
        img_urls = re.findall(r'src="(https?://.*?)"', html_body)
        for img_url in img_urls:
            try:
                # NEW FIX: Scrub HTML ampersands back to normal before downloading
                clean_url = img_url.replace('&amp;', '&')
                
                # Fetch using the clean URL
                img_response = requests.get(clean_url, timeout=10)
                
                if img_response.status_code == 200:
                    b64_data = base64.b64encode(img_response.content).decode('utf-8')
                    b64_src = f"data:image/png;base64,{b64_data}"
                    # Replace using the original escaped URL so the HTML matches
                    html_body = html_body.replace(img_url, b64_src)
                else:
                    print(f"[DEBUG] Google blocked the image download. Status: {img_response.status_code}")
            except Exception as e:
                print(f"[DEBUG] Failed to embed image in PDF: {e}")
        # ================================
        '''
        # === PRE-FETCH & EMBED IMAGES (BULLETPROOF BASE64) ===
        def fetch_and_encode_image(match):
            img_tag = match.group(0)
            # Scrub HTML ampersands back to normal before downloading
            img_url = match.group(1).replace("&amp;", "&") 
            try:
                # Force Python to download the image natively
                response = requests.get(img_url, timeout=10)
                if response.status_code == 200:
                    img_base64 = base64.b64encode(response.content).decode('utf-8')
                    # Inject the raw image data directly into the HTML tag
                    return img_tag.replace(match.group(1), f"data:image/png;base64,{img_base64}")
                else:
                    print(f"[DEBUG] Google blocked the image download. Status: {response.status_code}")
            except Exception as e:
                print(f"[DEBUG] Base64 Image Error: {str(e)}")
            
            return img_tag # Fallback to original if it fails

        # Find all <img> tags and replace their URLs with baked-in Base64 data
        html_body = re.sub(r'<img[^>]+src="([^">]+)"', fetch_and_encode_image, html_body)
        # =====================================================

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
                img {{ max-width: 450px; display: block; margin: 15px auto; }}
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
        unique_id = uuid.uuid4().hex[:8]
        # Use the SGT variable we created above for the filename
        timestamp = local_time_now.strftime("%Y%m%d_%H%M%S")
        blob_name = f"pdfs/Financial_Report_{timestamp}_{unique_id}.pdf"

        storage_client = storage.Client()
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(blob_name)
        blob.upload_from_file(pdf_buffer, content_type='application/pdf')
        
        # 5. ENVIRONMENT-AWARE SIGNED URL
        credentials, project_id = google.auth.default()
        
        if not hasattr(credentials, 'signer'):
            # Production Flow (Uses IAM to sign on behalf of the service account)
            request = google.auth.transport.requests.Request()
            credentials.refresh(request)
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=15),
                method="GET",
                service_account_email=credentials.service_account_email,
                access_token=credentials.token   
            )
        else:
            # Local Flow (Uses your key.json file automatically)
            url = blob.generate_signed_url(
                version="v4",
                expiration=timedelta(minutes=15), 
                method="GET"
            )

        # <--- FIX 3: UX-friendly message with inline code backticks to protect the URL
        return f"✅ **PDF Generated Successfully!** \n\n**[📥 Click Here to Open PDF Report]({url})** \n*(Note: For security, this link expires in 1 hour. Please download the report as soon as possible to save the report.)*"
        
    except Exception as e:
        return f"Error generating PDF: {str(e)}"