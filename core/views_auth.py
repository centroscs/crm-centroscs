from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.urls import reverse


def login_view(request):
    # se già loggato, vai dove ti manda next oppure in CRM
    if request.user.is_authenticated:
        return redirect(request.GET.get("next") or "crm_dashboard")

    error = None

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "").strip()

        user = authenticate(request, username=username, password=password)
        if user is None:
            error = "Credenziali non valide."
        else:
            login(request, user)
            return redirect(request.POST.get("next") or request.GET.get("next") or "crm_dashboard")

    return render(request, "core/login.html", {"error": error, "next": request.GET.get("next", "")})


@login_required
def logout_view(request):
    logout(request)
    return redirect("login")
