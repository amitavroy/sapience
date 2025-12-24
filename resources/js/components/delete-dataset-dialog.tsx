import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { destroy } from '@/routes/organisations/datasets';
import { type Dataset, type Organisation } from '@/types';
import { router } from '@inertiajs/react';
import { Trash2 } from 'lucide-react';
import { useState } from 'react';

interface DeleteDatasetDialogProps {
  organisation: Organisation;
  dataset: Dataset;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DeleteDatasetDialog({
  organisation,
  dataset,
  open,
  onOpenChange,
}: DeleteDatasetDialogProps) {
  const [deleteFiles, setDeleteFiles] = useState(false);
  const [deleteConversations, setDeleteConversations] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const handleDelete = () => {
    setIsDeleting(true);
    router.delete(
      destroy({
        organisation: organisation.uuid,
        dataset: dataset.uuid,
      }).url,
      {
        data: {
          delete_files: deleteFiles,
          delete_conversations: deleteConversations,
        },
        preserveScroll: false,
        onSuccess: () => {
          onOpenChange(false);
        },
        onError: () => {
          alert('Failed to delete dataset. Please try again.');
          setIsDeleting(false);
        },
        onFinish: () => {
          setIsDeleting(false);
        },
      },
    );
  };

  const handleOpenChange = (newOpen: boolean) => {
    if (!newOpen && !isDeleting) {
      // Reset state when dialog closes
      setDeleteFiles(false);
      setDeleteConversations(false);
    }
    onOpenChange(newOpen);
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="destructive">
          <Trash2 className="mr-2 size-4" />
          Delete Dataset
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete Dataset</DialogTitle>
          <DialogDescription>
            Are you sure you want to delete "{dataset.name}"? This action cannot
            be undone.
            <span className="mt-2 block">
              The Typesense collection will be deleted. You can choose to also
              delete associated files and conversations below.
            </span>
          </DialogDescription>
        </DialogHeader>
        <div className="space-y-4 py-4">
          <div className="flex items-start space-x-3">
            <Checkbox
              id="delete-files"
              checked={deleteFiles}
              onCheckedChange={(checked) => setDeleteFiles(checked === true)}
              disabled={isDeleting}
            />
            <div className="space-y-1">
              <Label
                htmlFor="delete-files"
                className="text-sm leading-none font-medium peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
              >
                Delete associated files
              </Label>
              <p className="text-xs text-muted-foreground">
                This will permanently delete {dataset.files_count || 0} file
                {dataset.files_count !== 1 ? 's' : ''} from storage. Files that
                belong to other datasets will not be deleted.
              </p>
            </div>
          </div>
          <div className="flex items-start space-x-3">
            <Checkbox
              id="delete-conversations"
              checked={deleteConversations}
              onCheckedChange={(checked) =>
                setDeleteConversations(checked === true)
              }
              disabled={isDeleting}
            />
            <div className="space-y-1">
              <Label
                htmlFor="delete-conversations"
                className="text-sm leading-none font-medium peer-disabled:cursor-not-allowed peer-disabled:opacity-70"
              >
                Delete associated conversations
              </Label>
              <p className="text-xs text-muted-foreground">
                This will permanently delete {dataset.conversations_count || 0}{' '}
                conversation
                {dataset.conversations_count !== 1 ? 's' : ''} and all their
                messages.
              </p>
            </div>
          </div>
        </div>
        <DialogFooter className="gap-2">
          <DialogClose asChild>
            <Button variant="secondary" disabled={isDeleting}>
              Cancel
            </Button>
          </DialogClose>
          <Button
            variant="destructive"
            onClick={handleDelete}
            disabled={isDeleting}
          >
            {isDeleting ? 'Deleting...' : 'Delete Dataset'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
