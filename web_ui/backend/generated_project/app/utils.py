import os
import secrets
from PIL import Image
from flask import current_app

def allowed_file(filename):
    """Check if file extension is allowed."""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']

def secure_filename_custom(filename):
    """Generate a secure filename with timestamp."""
    if not filename:
        return None
    
    # Get file extension
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    
    # Generate secure random filename
    random_hex = secrets.token_hex(16)
    return f"{random_hex}.{ext}" if ext else random_hex

def save_image(form_image, bear_id):
    """Save uploaded image with thumbnail generation."""
    try:
        if not form_image or not allowed_file(form_image.filename):
            return None
        
        # Generate secure filename
        filename = secure_filename_custom(form_image.filename)
        if not filename:
            return None
        
        # Create paths
        upload_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
        thumbnail_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'thumbnails', filename)
        
        # Open and process image
        image = Image.open(form_image)
        
        # Convert RGBA to RGB if necessary
        if image.mode in ('RGBA', 'LA', 'P'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            if image.mode == 'P':
                image = image.convert('