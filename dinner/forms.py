from django import forms

CUISINES = [
    ("any", "Any"),
    ("chinese", "Chinese"),
    ("japanese", "Japanese"),
    ("korean", "Korean"),
    ("italian", "Italian"),
    ("indian", "Indian"),
    ("mexican", "Mexican"),
    ("american", "American"),
]

PRICE = [
    ("any", "Any"),
    ("$", "$"),
    ("$$", "$$"),
    ("$$$", "$$$"),
]

DIETS = [
    ("none", "No preference"),
    ("vegetarian", "Vegetarian"),
    ("vegan", "Vegan"),
    ("halal", "Halal"),
    ("gluten_free", "Gluten-free"),
]


class PreferenceForm(forms.Form):
    cuisine = forms.ChoiceField(choices=CUISINES, required=False, initial="any")
    price = forms.ChoiceField(choices=PRICE, required=False, initial="any")
    diet = forms.ChoiceField(choices=DIETS, required=False, initial="none")
    near = forms.CharField(
        required=False,
        help_text="Address or city (optional)",
        label="Near",
    )
