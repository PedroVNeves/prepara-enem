from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import AlunoProfile, Escola, Professor, Turma, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ["email"]
    list_display = ["email", "nome", "is_staff", "is_active"]
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Dados pessoais", {"fields": ("nome",)}),
        (
            "Permissões",
            {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")},
        ),
        ("Datas", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "nome", "password1", "password2"),
            },
        ),
    )
    readonly_fields = ["date_joined"]
    search_fields = ["email", "nome"]


@admin.register(Escola)
class EscolaAdmin(admin.ModelAdmin):
    list_display = ["nome", "cnpj"]
    search_fields = ["nome", "cnpj"]


@admin.register(Professor)
class ProfessorAdmin(admin.ModelAdmin):
    list_display = ["user", "escola", "cargo"]
    list_filter = ["escola", "cargo"]


@admin.register(Turma)
class TurmaAdmin(admin.ModelAdmin):
    list_display = ["nome", "escola", "ano_letivo"]
    list_filter = ["escola", "ano_letivo"]


@admin.register(AlunoProfile)
class AlunoProfileAdmin(admin.ModelAdmin):
    list_display = ["user", "escola", "turma"]
    list_filter = ["escola", "turma"]
