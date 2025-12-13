import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Spinner } from '@/components/ui/spinner';
import { formatRelativeTime } from '@/lib/utils';
import { destroy as destroyConversation } from '@/routes/organisations/conversations';
import { show as conversationShow } from '@/routes/organisations/datasets/conversations';
import { type Conversation, type Organisation, type User } from '@/types';
import { Link, router } from '@inertiajs/react';
import { Trash2 } from 'lucide-react';
import { useState } from 'react';

interface ConversationCardProps {
  conversation: Conversation;
  organisation: Organisation;
  currentUser: User;
  onDelete?: () => void;
}

export function ConversationCard({
  conversation,
  organisation,
  currentUser,
  onDelete,
}: ConversationCardProps) {
  const [deleting, setDeleting] = useState(false);
  const [dialogOpen, setDialogOpen] = useState(false);
  const isOwner = conversation.user.id === currentUser.id;

  const handleDelete = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();

    setDeleting(true);
    router.delete(
      destroyConversation.url({
        organisation: organisation.uuid,
        conversation: conversation.uuid,
      }),
      {
        preserveScroll: true,
        onSuccess: () => {
          setDialogOpen(false);
          if (onDelete) {
            onDelete();
          }
        },
        onError: () => {
          alert('Failed to delete conversation. Please try again.');
          setDeleting(false);
        },
        onFinish: () => {
          setDeleting(false);
        },
      },
    );
  };

  const conversationUrl = conversationShow({
    organisation: organisation.uuid,
    dataset: conversation.dataset.uuid,
    conversation: conversation.uuid,
  }).url;

  return (
    <div className="group relative flex items-center justify-between px-4 py-3 transition-colors hover:bg-accent">
      <Link href={conversationUrl} className="flex-1">
        <div className="flex flex-col">
          <div className="mb-1 flex items-center gap-2">
            <h3 className="font-semibold text-foreground group-hover:text-primary">
              {conversation.title || 'Untitled Conversation'}
            </h3>
            <Badge variant="secondary" className="text-xs">
              {conversation.dataset.name}
            </Badge>
          </div>
          <div className="text-sm text-muted-foreground">
            Last message {formatRelativeTime(conversation.updated_at)}
          </div>
        </div>
      </Link>
      {isOwner && (
        <div
          className="ml-4 opacity-0 transition-opacity group-hover:opacity-100"
          onClick={(e) => e.stopPropagation()}
        >
          <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
            <DialogTrigger asChild>
              <Button
                variant="ghost"
                size="icon"
                className="size-8 text-muted-foreground hover:text-destructive"
                disabled={deleting}
                onClick={(e) => {
                  e.stopPropagation();
                }}
              >
                {deleting ? <Spinner /> : <Trash2 className="size-4" />}
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogTitle>Delete Conversation</DialogTitle>
              <DialogDescription>
                Are you sure you want to delete "
                {conversation.title || 'Untitled Conversation'}"?
                <span className="mt-2 block">
                  This will permanently delete the conversation and all its
                  messages. This action cannot be undone.
                </span>
              </DialogDescription>
              <DialogFooter className="gap-2">
                <DialogClose asChild>
                  <Button variant="secondary">Cancel</Button>
                </DialogClose>
                <Button
                  variant="destructive"
                  onClick={handleDelete}
                  disabled={deleting}
                >
                  {deleting ? (
                    <>
                      <Spinner />
                      Deleting...
                    </>
                  ) : (
                    'Delete'
                  )}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>
      )}
    </div>
  );
}
