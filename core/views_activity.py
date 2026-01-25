from django.shortcuts import render, redirect


def activity_list(request):
    # template già presente
    return render(request, "core/agent_calendar.html")


def activity_add(request):
    if request.method == "POST":
        return redirect("activity_list")
    return render(request, "core/activity_form.html")

