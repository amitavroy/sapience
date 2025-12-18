import DatasetInfo from '@/components/dataset-info';
import { DeleteDatasetDialog } from '@/components/delete-dataset-dialog';
import FileUpload from '@/components/file-upload';
import FilesTable, { type FilesTableRef } from '@/components/files-table';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import AppLayout from '@/layouts/app-layout';
import { dashboard } from '@/routes/organisations';
import { edit, index, show } from '@/routes/organisations/datasets';
import { type BreadcrumbItem, type Dataset, type Organisation } from '@/types';
import { Head, Link } from '@inertiajs/react';
import { useRef, useState } from 'react';

interface ShowProps {
  organisation: Organisation;
  dataset: Dataset;
  isAdmin: boolean;
}

export default function DatasetShow({
  organisation,
  dataset,
  isAdmin,
}: ShowProps) {
  const filesTableRef = useRef<FilesTableRef>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

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
    {
      title: dataset.name,
      href: show({
        organisation: organisation.uuid,
        dataset: dataset.uuid,
      }).url,
    },
  ];

  return (
    <AppLayout breadcrumbs={breadcrumbs}>
      <Head title={`${dataset.name} - ${organisation.name}`} />
      <div className="flex h-full flex-1 flex-col gap-4 overflow-x-auto rounded-xl p-4">
        <div className="mb-4 flex items-center justify-between">
          <div>
            <div className="mb-2 flex items-center gap-3">
              <h1 className="text-2xl font-bold">{dataset.name}</h1>
              <Badge variant={dataset.is_active ? 'default' : 'secondary'}>
                {dataset.is_active ? 'Active' : 'Inactive'}
              </Badge>
            </div>
            {dataset.description && (
              <p className="text-muted-foreground">{dataset.description}</p>
            )}
          </div>
          {isAdmin && (
            <div className="flex gap-2">
              <Link
                href={
                  edit({
                    organisation: organisation.uuid,
                    dataset: dataset.uuid,
                  }).url
                }
              >
                <Button variant="outline">Edit Dataset</Button>
              </Link>
              <DeleteDatasetDialog
                organisation={organisation}
                dataset={dataset}
                open={deleteDialogOpen}
                onOpenChange={setDeleteDialogOpen}
              />
            </div>
          )}
        </div>

        <div className="flex flex-col gap-6 md:flex-row">
          <div className="flex-[0.4]">
            <DatasetInfo dataset={dataset} organisation={organisation} />
          </div>

          <div className="flex-[0.6] rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
            <h2 className="mb-4 text-lg font-semibold">Upload Files</h2>
            <FileUpload
              organisation={organisation}
              dataset={dataset}
              onUploadComplete={() => {
                // Files table will refresh automatically via its own fetch
              }}
              onFilesValidated={(files) => {
                filesTableRef.current?.addFiles(files);
              }}
            />
          </div>
        </div>

        <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
          <h2 className="mb-4 text-lg font-semibold">Files</h2>
          <FilesTable
            ref={filesTableRef}
            organisation={organisation}
            dataset={dataset}
          />
        </div>
      </div>
    </AppLayout>
  );
}
