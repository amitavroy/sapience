import DatasetForm from '@/components/dataset-form';
import AppLayout from '@/layouts/app-layout';
import { type BreadcrumbItem, type Dataset, type Organisation } from '@/types';
import { Head } from '@inertiajs/react';

interface EditProps {
    organisation: Organisation;
    dataset: Dataset;
}

export default function DatasetEdit({ organisation, dataset }: EditProps) {
    const breadcrumbs: BreadcrumbItem[] = [
        {
            title: 'Organisations',
            href: '#',
        },
        {
            title: organisation.name,
            href: '#',
        },
        {
            title: 'Datasets',
            href: '#',
        },
        {
            title: dataset.name,
            href: '#',
        },
        {
            title: 'Edit',
            href: '#',
        },
    ];

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title={`Edit Dataset - ${dataset.name}`} />
            <div className="flex h-full flex-1 flex-col gap-4 overflow-x-auto rounded-xl p-4">
                <div className="mb-4">
                    <h1 className="text-2xl font-bold">Edit Dataset</h1>
                    <p className="text-muted-foreground">
                        Update dataset information
                    </p>
                </div>

                <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
                    <DatasetForm
                        type="edit"
                        organisation={organisation}
                        dataset={dataset}
                    />
                </div>
            </div>
        </AppLayout>
    );
}
