import { Button } from '@/components/ui/button';
import { store } from '@/routes/organisations/datasets/conversations';
import { type Dataset, type Organisation } from '@/types';
import { router } from '@inertiajs/react';
import { useState } from 'react';

interface DatasetInfoProps {
  dataset: Dataset;
  organisation: Organisation;
}

export default function DatasetInfo({
  dataset,
  organisation,
}: DatasetInfoProps) {
  const [isCreating, setIsCreating] = useState(false);

  const handleCreateConversation = () => {
    setIsCreating(true);
    router.post(
      store({
        organisation: organisation.uuid,
        dataset: dataset.uuid,
      }).url,
      {},
      {
        onFinish: () => setIsCreating(false),
      },
    );
  };

  return (
    <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
      <div className="grid gap-4 md:grid-cols-2">
        <div>
          <h3 className="mb-1 text-sm font-medium text-muted-foreground">
            Status
          </h3>
          <p className="text-sm">{dataset.is_active ? 'Active' : 'Inactive'}</p>
        </div>
        <div>
          <h3 className="mb-1 text-sm font-medium text-muted-foreground">
            Files
          </h3>
          <p className="text-sm">
            {dataset.files_count} file
            {dataset.files_count !== 1 ? 's' : ''}
          </p>
        </div>
        <div>
          <h3 className="mb-1 text-sm font-medium text-muted-foreground">
            Owner
          </h3>
          <p className="text-sm">{dataset.owner.name}</p>
        </div>
        <div>
          <h3 className="mb-1 text-sm font-medium text-muted-foreground">
            Created
          </h3>
          <p className="text-sm">
            {dataset.created_at
              ? new Date(dataset.created_at).toLocaleDateString()
              : 'N/A'}
          </p>
        </div>
        <div>
          <h3 className="mb-1 text-sm font-medium text-muted-foreground">
            Updated
          </h3>
          <p className="text-sm">
            {dataset.updated_at
              ? new Date(dataset.updated_at).toLocaleDateString()
              : 'N/A'}
          </p>
        </div>
      </div>
      <div className="mt-6">
        <Button
          className="w-full"
          onClick={handleCreateConversation}
          disabled={isCreating}
        >
          {isCreating ? 'Creating...' : 'Create conversation'}
        </Button>
      </div>
    </div>
  );
}
