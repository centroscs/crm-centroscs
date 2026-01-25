from django import forms
from django.utils import timezone


class ActivityForm(forms.Form):
    TYPE_CHOICES = (
        ("appointment", "Appuntamento (calendario generale)"),
        ("todo", "To-Do (solo calendario agente)"),
    )

    activity_type = forms.ChoiceField(label="Tipologia", choices=TYPE_CHOICES)

    title = forms.CharField(label="Titolo", max_length=200)

    # Campi per appuntamento
    start = forms.DateTimeField(
        label="Inizio (YYYY-MM-DD HH:MM)",
        required=False,
        input_formats=["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"],
    )
    end = forms.DateTimeField(
        label="Fine (YYYY-MM-DD HH:MM)",
        required=False,
        input_formats=["%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M"],
    )
    location = forms.CharField(label="Luogo", max_length=250, required=False)

    # Campi per todo
    due_date = forms.DateField(
        label="Scadenza (YYYY-MM-DD)",
        required=False,
        input_formats=["%Y-%m-%d"],
    )

    notes = forms.CharField(label="Note", required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def clean(self):
        cleaned = super().clean()
        t = cleaned.get("activity_type")

        if t == "appointment":
            start = cleaned.get("start")
            end = cleaned.get("end")
            if not start or not end:
                raise forms.ValidationError("Per un appuntamento devi inserire Inizio e Fine.")
            if end <= start:
                raise forms.ValidationError("La Fine deve essere successiva all’Inizio.")
        elif t == "todo":
            # scadenza opzionale, ok.
            pass
        else:
            raise forms.ValidationError("Tipologia non valida.")

        return cleaned
