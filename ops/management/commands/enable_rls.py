from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = (
        "Habilita Row Level Security em todas as tabelas do schema public, sem "
        "adicionar policies. Bloqueia acesso via PostgREST/chave anon do Supabase; "
        "não afeta a aplicação, que conecta como owner das tabelas (ignora RLS). "
        "Idempotente: reruns são seguros (ENABLE em tabela já habilitada é no-op)."
    )

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            tables = [row[0] for row in cursor.fetchall()]
            for table in tables:
                cursor.execute(f'ALTER TABLE public."{table}" ENABLE ROW LEVEL SECURITY;')
                self.stdout.write(f"  RLS habilitado: {table}")
        self.stdout.write(self.style.SUCCESS(f"{len(tables)} tabelas processadas."))
