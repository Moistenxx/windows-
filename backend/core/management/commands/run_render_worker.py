from django.core.management.base import BaseCommand

from core.models import Job
from core.views import complete_render_job


class Command(BaseCommand):
    help = "Render queued jobs that already have source_asset_ids."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=10)

    def handle(self, *args, **options):
        rendered = 0
        for job in Job.objects.filter(status=Job.PENDING, output_asset__isnull=True).order_by("created_at", "id"):
            if not job.render.get("source_asset_ids"):
                continue
            complete_render_job(job.id)
            rendered += 1
            if rendered >= options["limit"]:
                break
        self.stdout.write(f"rendered {rendered}")
