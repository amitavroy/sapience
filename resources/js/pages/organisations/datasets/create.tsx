import DatasetForm from '@/components/dataset-form';
import AppLayout from '@/layouts/app-layout';
import { type BreadcrumbItem, type Dataset, type Organisation } from '@/types';
import { Head } from '@inertiajs/react';

interface CreateProps {
    organisation: Organisation;
    dataset: Dataset;
}

export default function DatasetCreate({ organisation, dataset }: CreateProps) {
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
            title: 'Create',
            href: '#',
        },
    ];

    return (
        <AppLayout breadcrumbs={breadcrumbs}>
            <Head title={`Create Dataset - ${organisation.name}`} />
            <div className="flex h-full flex-1 flex-col gap-4 overflow-x-auto rounded-xl p-4">
                <div className="mb-4">
                    <h1 className="text-2xl font-bold">Create Dataset</h1>
                    <p className="text-muted-foreground">
                        Create a new dataset for {organisation.name}
                    </p>
                </div>

                <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
                    <DatasetForm
                        type="create"
                        organisation={organisation}
                        dataset={dataset}
                    />
                </div>
            </div>
        </AppLayout>
    );
}
