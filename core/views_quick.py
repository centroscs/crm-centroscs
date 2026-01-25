from django.shortcuts import render, redirect


def quick(request):
    # puoi decidere una pagina quick, intanto riuso la dashboard
    return render(request, "core/dashboard.html")


def appointment_quick_create(request):
    if request.method == "POST":
        return redirect("crm_appointment_list")
    return render(request, "core/appointment_form.html", {"mode": "quick"})
