import os
import re
from PIL import Image, ImageEnhance, ImageFilter
import pytesseract


def get_sorted_image_files(directory_path):
    """Get sorted list of image file paths from a directory.
    
    Returns list of (filename, full_path) tuples sorted by filename.
    """
    valid_exts = {'.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif'}
    results = []
    if os.path.exists(directory_path):
        for filename in sorted(os.listdir(directory_path)):
            ext = os.path.splitext(filename)[1].lower()
            if ext in valid_exts:
                full_path = os.path.join(directory_path, filename)
                results.append((filename, full_path))
    return results


def preprocess_image(image_path, scale_factor=2, contrast_factor=2.0, threshold=140):
    """Preprocess a receipt image for OCR.
    
    Pipeline:
    1. Open and convert to grayscale
    2. Upscale by scale_factor using LANCZOS
    3. Enhance contrast
    4. Apply median filter for denoising
    5. Binarize with threshold
    
    Returns: PIL Image object ready for OCR
    """
    img = Image.open(image_path)
    
    # Convert to grayscale (handles RGBA, RGB, etc.)
    gray = img.convert('L')
    
    # Upscale
    w, h = gray.size
    upscaled = gray.resize(
        (w * scale_factor, h * scale_factor),
        resample=Image.Resampling.LANCZOS
    )
    
    # Enhance contrast
    enhancer = ImageEnhance.Contrast(upscaled)
    enhanced = enhancer.enhance(contrast_factor)
    
    # Denoise with median filter
    denoised = enhanced.filter(ImageFilter.MedianFilter(size=3))
    
    # Binarize
    binary = denoised.point(lambda p: 255 if p > threshold else 0, mode='1')
    
    return binary


def extract_text_from_image(image_path, psm=4, oem=3, scale_factor=2, 
                             contrast_factor=2.0, threshold=140):
    """Extract text from a receipt image using preprocessing + Tesseract.
    
    Args:
        image_path: Path to the image file
        psm: Page segmentation mode (4=single column, 6=uniform block)
        oem: OCR engine mode (3=default LSTM+legacy)
        scale_factor: Image upscale factor
        contrast_factor: Contrast enhancement factor
        threshold: Binarization threshold (0-255)
    
    Returns: Extracted text string, cleaned of non-printable chars
    """
    # Preprocess
    processed_img = preprocess_image(
        image_path, 
        scale_factor=scale_factor,
        contrast_factor=contrast_factor,
        threshold=threshold
    )
    
    # Configure Tesseract
    config = f'--oem {oem} --psm {psm}'
    
    # Extract text
    text = pytesseract.image_to_string(processed_img, config=config)
    
    # Clean: remove form feed and non-printable characters
    text = text.replace('\x0c', '')
    # Keep printable ASCII + newlines + common chars
    text = re.sub(r'[^\x20-\x7E\n]', '', text)
    
    return text.strip()


def extract_text_multi_config(image_path):
    """Try multiple OCR configurations and return the best result.
    
    Tries PSM 4 (column) first, then PSM 6 (block) if result is too short.
    Also tries different preprocessing parameters.
    """
    # Primary attempt: PSM 4, standard preprocessing
    text1 = extract_text_from_image(image_path, psm=4)
    
    # If result is very short, try PSM 6
    if len(text1.strip()) < 50:
        text2 = extract_text_from_image(image_path, psm=6)
        if len(text2.strip()) > len(text1.strip()):
            text1 = text2
    
    # If still short, try with different threshold
    if len(text1.strip()) < 50:
        text3 = extract_text_from_image(image_path, psm=4, threshold=128)
        if len(text3.strip()) > len(text1.strip()):
            text1 = text3
    
    return text1
