from django.shortcuts import render, redirect


def todo_list(request):
    return render(request, "core/agent_todos.html")


def todo_add(request):
    if request.method == "POST":
        return redirect("todo_list")
    return render(request, "core/todo_form.html")


def todo_done(request, pk: int):
    # per ora: chiude e torna lista
    return redirect("todo_list")
