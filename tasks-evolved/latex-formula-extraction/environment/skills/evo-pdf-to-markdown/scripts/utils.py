import os

def setup_marker_models():
    """
    Initialize the dictionary of deep learning models for marker-pdf.
    Returns the model dictionary needed by PdfConverter.
    """
    from marker.models import create_model_dict
    model_dict = create_model_dict()
    return model_dict

def convert_pdf_to_markdown(pdf_path, force_ocr=False):
    """
    Converts a PDF file to Markdown using marker-pdf 1.3.3.
    
    Args:
        pdf_path (str): Path to the PDF file.
        force_ocr (bool): Whether to force OCR processing.
    
    Returns:
        str: Markdown text with LaTeX formulas preserved in $$ delimiters.
    """
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.output import text_from_rendered
    
    config_dict = {}
    if force_ocr:
        config_dict["force_ocr"] = True
    
    model_dict = create_model_dict()
    
    if config_dict:
        from marker.config.parser import ConfigParser
        config_parser = ConfigParser(config_dict)
        converter = PdfConverter(
            artifact_dict=model_dict,
            config=config_parser.generate_config_dict()
        )
    else:
        converter = PdfConverter(artifact_dict=model_dict)
    
    rendered_document = converter(pdf_path)
    text, metadata, images = text_from_rendered(rendered_document)
    
    return text
