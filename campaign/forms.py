from django import forms
from .models import Participant, Document


class ParticipantForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = [
            "full_name", "mobile_number", "email", "date_of_birth",
            "address", "college_name", "plus_two_completion_year",
        ]
        widgets = {
            "date_of_birth": forms.DateInput(attrs={"type": "date"}),
            "address": forms.Textarea(attrs={"rows": 3}),
        }


class DocumentUploadForm(forms.Form):
    plus2_certificate = forms.FileField(
        label="+2 Pass Certificate / Marksheet",
        validators=[],  # add FileExtensionValidator + size check below
    )