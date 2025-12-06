import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import AppLayout from '@/layouts/app-layout';
import { dashboard } from '@/routes/organisations';
import { create, index } from '@/routes/organisations/datasets';
import { type BreadcrumbItem, type Dataset, type Organisation } from '@/types';
import { Head, Link } from '@inertiajs/react';

interface IndexProps {
  organisation: Organisation;
  datasets: Dataset[];
  isAdmin: boolean;
}

export default function DatasetsIndex({
  organisation,
  datasets,
  isAdmin,
}: IndexProps) {
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
      title: 'Datasets',
      href: index(organisation.uuid).url,
    },
  ];

  return (
    <AppLayout breadcrumbs={breadcrumbs}>
      <Head title={`Datasets - ${organisation.name}`} />
      <div className="flex h-full flex-1 flex-col gap-4 overflow-x-auto rounded-xl p-4">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Datasets</h1>
            <p className="text-muted-foreground">
              Manage datasets for {organisation.name}
            </p>
          </div>
          {isAdmin && (
            <Link href={create(organisation.uuid).url}>
              <Button>Create Dataset</Button>
            </Link>
          )}
        </div>

        {datasets.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-sidebar-border/70 p-12 text-center dark:border-sidebar-border">
            <p className="text-muted-foreground">
              No datasets found.{' '}
              {isAdmin && 'Create your first dataset to get started.'}
            </p>
          </div>
        ) : (
          <div className="grid gap-4">
            {datasets.map((dataset) => (
              <Link
                key={dataset.id}
                href={`/organisations/${organisation.uuid}/datasets/${dataset.uuid}`}
                className="group rounded-xl border border-sidebar-border/70 p-6 transition-colors hover:bg-accent dark:border-sidebar-border"
              >
                <div className="flex items-start justify-between">
                  <div className="flex-1">
                    <div className="mb-2 flex items-center gap-3">
                      <h3 className="text-lg font-semibold group-hover:text-primary">
                        {dataset.name}
                      </h3>
                      <Badge
                        variant={dataset.is_active ? 'default' : 'secondary'}
                      >
                        {dataset.is_active ? 'Active' : 'Inactive'}
                      </Badge>
                    </div>
                    {dataset.description && (
                      <p className="mb-3 text-sm text-muted-foreground">
                        {dataset.description}
                      </p>
                    )}
                    <div className="flex items-center gap-4 text-sm text-muted-foreground">
                      <span>
                        {dataset.files_count} file
                        {dataset.files_count !== 1 ? 's' : ''}
                      </span>
                      <span>Owner: {dataset.owner.name}</span>
                    </div>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
