from django.contrib import admin

from .models import Alternative, Exam, Question, Topic


class AlternativeInline(admin.TabularInline):
    model = Alternative
    extra = 0


@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ["year", "title"]


@admin.register(Topic)
class TopicAdmin(admin.ModelAdmin):
    list_display = ["name", "discipline"]
    list_filter = ["discipline"]
    search_fields = ["name"]


@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ["exam", "external_index", "discipline", "language", "topic"]
    list_filter = ["exam", "discipline", "language"]
    search_fields = ["context"]
    inlines = [AlternativeInline]
