from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, TextAreaField, FloatField, BooleanField, SelectField, SubmitField
from wtforms.validators import DataRequired, Email, Length, NumberRange, Optional
from wtforms.widgets import TextArea

class TeddyBearForm(FlaskForm):
    """Form for adding/editing teddy bears."""
    name = StringField('Naam', validators=[DataRequired(), Length(max=100)])
    brand = StringField('Merk', validators=[DataRequired(), Length(max=50)])
    description = TextAreaField('Beschrijving', widget=TextArea())
    height = FloatField('Hoogte (cm)', validators=[Optional(), NumberRange(min=0)])
    width = FloatField('Breedte (cm)', validators=[Optional(), NumberRange(min=0)])
    material = StringField('Materiaal', validators=[Length(max=100)])
    colors = StringField('Kleuren (gescheiden door komma\'s)', validators=[Length(max=200)])
    price = FloatField('Prijs (€)', validators=[Optional(), NumberRange(min=0)])
    category = SelectField('Categorie', choices=[
        ('', 'Selecteer categorie'),
        ('klassiek', 'Klassieke Knuffelberen'),
        ('vintage', 'Vintage Collectie'),
        ('designer', 'Designer Bears'),
        ('baby', 'Baby Knuffels'),
        ('groot', 'Grote Knuffelberen'),
        ('klein', 'Mini Knuffelberen'),
        ('speciaal', 'Speciale Editie')
    ])
    tags = StringField('Tags (gescheiden door komma\'s)', validators=[Length(max=200)])
    is_available = BooleanField('Beschikbaar')
    featured = BooleanField('Featured (tonen op homepage)')
    submit = SubmitField('Opslaan')

class ImageUploadForm(FlaskForm):
    """Form for uploading bear images."""
    image = FileField('Afbeelding', validators=[
        FileRequired(),
        FileAllowed(['jpg', 'jpeg', 'png', 'gif', 'webp'], 'Alleen afbeeldingen toegestaan!')
    ])
    alt_text = StringField('Alt tekst', validators=[Length(max=255)])
    is_primary = BooleanField('Primaire afbeelding')
    submit = SubmitField('Upload')

class ContactForm(FlaskForm):
    """Contact form."""
    name = StringField('Naam', validators=[DataRequired(), Length(max=100)])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    subject = StringField('Onderwerp', validators=[Length(max=200)])
    message = TextAreaField('Bericht', validators=[DataRequired()], widget=TextArea())
    submit = SubmitField('Verstuur Bericht')

class SearchForm(FlaskForm):
    """Search form."""
    query = StringField('Zoeken...', validators=[Length(max=100)])
    category = SelectField('Categorie', choices=[
        ('', 'Alle categorieën'),
        ('klassiek', 'Klassieke Knuffelberen'),
        ('vintage', 'Vintage Collectie'),
        ('designer', 'Designer Bears'),
        ('baby', 'Baby Knuffels'),
        ('groot', 'Grote Knuffelberen'),
        ('klein', 'Mini Knuffelberen'),
        ('speciaal', 'Speciale Editie')
    ])
    brand = StringField('Merk', validators=[Length(max=50)])
    min_price = FloatField('Min. prijs (€)', validators=[Optional(), NumberRange(min=0)])
    max_price = FloatField('Max. prijs (€)', validators=[Optional(), NumberRange(min=0)])
    available_only = BooleanField('Alleen beschikbare items', default=True)
    submit = SubmitField('Zoeken')