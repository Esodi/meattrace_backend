from io import BytesIO
from django.template.loader import get_template
from xhtml2pdf import pisa
from django.http import HttpResponse
import logging

logger = logging.getLogger(__name__)

def render_to_pdf(template_src, context_dict={}):
    """
    Renders an HTML template to a PDF and returns the PDF content as bytes.
    """
    template = get_template(template_src)
    html  = template.render(context_dict)
    result = BytesIO()
    
    # Create the PDF
    pdf = pisa.pisaDocument(BytesIO(html.encode("utf-8")), result)
    
    if not pdf.err:
        return result.getvalue()
    
    logger.error(f"Error generating PDF: {pdf.err}")
    return None

def download_pdf_response(template_src, context_dict, filename):
    """
    Generates a PDF and returns it as a Django HttpResponse.
    """
    pdf_content = render_to_pdf(template_src, context_dict)
    if pdf_content:
        response = HttpResponse(pdf_content, content_type='application/pdf')
        content = f"attachment; filename='{filename}'"
        response['Content-Disposition'] = content
        return response
    return None
