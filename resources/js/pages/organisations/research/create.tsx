import ResearchForm from '@/components/research-form';
import AppLayout from '@/layouts/app-layout';
import { dashboard } from '@/routes/organisations';
import { index as researchIndex } from '@/routes/organisations/research';
import { type BreadcrumbItem, type Organisation, type Research } from '@/types';
import { Head } from '@inertiajs/react';

interface CreateProps {
  organisation: Organisation;
  research: Research;
}

export default function ResearchCreate({
  organisation,
  research,
}: CreateProps) {
  const breadcrumbs: BreadcrumbItem[] = [
    {
      title: 'Organisations',
      href: dashboard(organisation.uuid).url,
    },
    {
      title: organisation.name,
      href: dashboard(organisation.uuid).url,
    },
    {
      title: 'Research',
      href: researchIndex.url({ organisation: organisation.uuid }),
    },
    {
      title: 'Create',
      href: '#',
    },
  ];

  return (
    <AppLayout breadcrumbs={breadcrumbs}>
      <Head title={`Create Research - ${organisation.name}`} />
      <div className="flex h-full flex-1 flex-col gap-4 overflow-x-auto rounded-xl p-4">
        <div className="mb-4">
          <h1 className="text-2xl font-bold">Create Research</h1>
          <p className="text-muted-foreground">
            Create a new research for {organisation.name}
          </p>
        </div>

        <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
          <ResearchForm
            type="create"
            organisation={organisation}
            research={research}
          />
        </div>
      </div>
    </AppLayout>
  );
}
