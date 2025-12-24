import ResearchForm from '@/components/research-form';
import AppLayout from '@/layouts/app-layout';
import { dashboard } from '@/routes/organisations';
import {
  index as researchIndex,
  show as researchShow,
} from '@/routes/organisations/research';
import { type BreadcrumbItem, type Organisation, type Research } from '@/types';
import { Head } from '@inertiajs/react';

interface EditProps {
  organisation: Organisation;
  research: Research;
}

export default function ResearchEdit({ organisation, research }: EditProps) {
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
      title: research.query,
      href: researchShow({
        organisation: organisation.uuid,
        research: research.uuid,
      }).url,
    },
    {
      title: 'Edit',
      href: '#',
    },
  ];

  return (
    <AppLayout breadcrumbs={breadcrumbs}>
      <Head title={`Edit Research - ${research.query}`} />
      <div className="flex h-full flex-1 flex-col gap-4 overflow-x-auto rounded-xl p-4">
        <div className="mb-4">
          <h1 className="text-2xl font-bold">Edit Research</h1>
          <p className="text-muted-foreground">Update research information</p>
        </div>

        <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
          <ResearchForm
            type="edit"
            organisation={organisation}
            research={research}
          />
        </div>
      </div>
    </AppLayout>
  );
}
