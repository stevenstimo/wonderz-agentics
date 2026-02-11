from datetime import datetime
from app import db
from sqlalchemy import or_

class TeddyBear(db.Model):
    """Model for teddy bears."""
    __tablename__ = 'teddy_bears'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, index=True)
    brand = db.Column(db.String(50), nullable=False, index=True)
    description = db.Column(db.Text)
    height = db.Column(db.Float)  # in cm
    width = db.Column(db.Float)   # in cm
    material = db.Column(db.String(100))
    colors = db.Column(db.String(200))  # comma-separated colors
    price = db.Column(db.Float)
    category = db.Column(db.String(50), index=True)
    tags = db.Column(db.String(200))  # comma-separated tags
    is_available = db.Column(db.Boolean, default=True, index=True)
    featured = db.Column(db.Boolean, default=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    images = db.relationship('BearImage', backref='bear', lazy='dynamic', cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<TeddyBear {self.name}>'
    
    @property
    def primary_image(self):
        """Get the primary image for this bear."""
        return self.images.filter_by(is_primary=True).first()
    
    @property
    def color_list(self):
        """Get colors as a list."""
        return [color.strip() for color in (self.colors or '').split(',') if color.strip()]
    
    @property
    def tag_list(self):
        """Get tags as a list."""
        return [tag.strip() for tag in (self.tags or '').split(',') if tag.strip()]
    
    @classmethod
    def search(cls, query):
        """Search bears by name, brand, description, or tags."""
        if not query:
            return cls.query
        
        search_term = f"%{query}%"
        return cls.query.filter(
            or_(
                cls.name.ilike(search_term),
                cls.brand.ilike(search_term),
                cls.description.ilike(search_term),
                cls.tags.ilike(search_term),
                cls.category.ilike(search_term)
            )
        )
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'name': self.name,
            'brand': self.brand,
            'description': self.description,
            'height': self.height,
            'width': self.width,
            'material': self.material,
            'colors': self.color_list,
            'price': self.price,
            'category': self.category,
            'tags': self.tag_list,
            'is_available': self.is_available,
            'featured': self.featured,
            'primary_image': self.primary_image.filename if self.primary_image else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

class BearImage(db.Model):
    """Model for bear images."""
    __tablename__ = 'bear_images'
    
    id = db.Column(db.Integer, primary_key=True)
    bear_id = db.Column(db.Integer, db.ForeignKey('teddy_bears.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255))
    alt_text = db.Column(db.String(255))
    is_primary = db.Column(db.Boolean, default=False)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<BearImage {self.filename}>'

class ContactMessage(db.Model):
    """Model for contact form messages."""
    __tablename__ = 'contact_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    subject = db.Column(db.String(200))
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<ContactMessage from {self.email}>'