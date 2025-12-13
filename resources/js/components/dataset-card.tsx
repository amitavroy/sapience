import { Badge } from '@/components/ui/badge';
import { type Dataset, type Organisation } from '@/types';
import { Link } from '@inertiajs/react';

interface DatasetCardProps {
  dataset: Dataset;
  organisation: Organisation;
}

export function DatasetCard({ dataset, organisation }: DatasetCardProps) {
  return (
    <Link
      href={`/organisations/${organisation.uuid}/datasets/${dataset.uuid}`}
      className="group rounded-xl border border-sidebar-border/70 p-6 transition-colors hover:bg-accent dark:border-sidebar-border"
    >
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <div className="mb-2 flex items-center gap-3">
            <h3 className="text-lg font-semibold group-hover:text-primary">
              {dataset.name}
            </h3>
            <Badge variant={dataset.is_active ? 'default' : 'secondary'}>
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
              {dataset.files_count} file{dataset.files_count !== 1 ? 's' : ''}
            </span>
            <span>Owner: {dataset.owner.name}</span>
          </div>
        </div>
      </div>
    </Link>
  );
}
