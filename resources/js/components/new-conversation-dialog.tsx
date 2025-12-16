import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { store } from '@/routes/organisations/datasets/conversations';
import { type Dataset, type Organisation } from '@/types';
import { router } from '@inertiajs/react';
import { useState } from 'react';

interface NewConversationDialogProps {
  organisation: Organisation;
  datasets: Dataset[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function NewConversationDialog({
  organisation,
  datasets,
  open,
  onOpenChange,
}: NewConversationDialogProps) {
  const [selectedDatasetId, setSelectedDatasetId] = useState<string>('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleClose = () => {
    onOpenChange(false);
    setSelectedDatasetId('');
  };

  const handleSubmit = () => {
    if (!selectedDatasetId) {
      return;
    }

    const selectedDataset = datasets.find((d) => d.uuid === selectedDatasetId);
    if (!selectedDataset) {
      return;
    }

    setIsSubmitting(true);
    const route = store({
      organisation: organisation.uuid,
      dataset: selectedDataset.uuid,
    });

    router.post(route.url, {}, {
      onFinish: () => {
        setIsSubmitting(false);
        handleClose();
      },
      onError: () => {
        setIsSubmitting(false);
      },
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Chat</DialogTitle>
          <DialogDescription>
            Select the dataset you want to chat with
          </DialogDescription>
        </DialogHeader>
        <div className="py-4">
          {datasets.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No active datasets available. Please create a dataset first.
            </p>
          ) : (
            <Select
              value={selectedDatasetId}
              onValueChange={setSelectedDatasetId}
            >
              <SelectTrigger>
                <SelectValue placeholder="Select a dataset" />
              </SelectTrigger>
              <SelectContent>
                {datasets.map((dataset) => (
                  <SelectItem key={dataset.uuid} value={dataset.uuid}>
                    {dataset.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={handleClose}
            disabled={isSubmitting}
          >
            Cancel
          </Button>
          <Button
            onClick={handleSubmit}
            disabled={!selectedDatasetId || isSubmitting || datasets.length === 0}
          >
            {isSubmitting ? 'Creating...' : 'Create Chat'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

