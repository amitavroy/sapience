import { ConversationCard } from '@/components/conversation-card';
import { NewConversationDialog } from '@/components/new-conversation-dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import AppLayout from '@/layouts/app-layout';
import { dashboard } from '@/routes/organisations';
import { index as conversationsIndex } from '@/routes/organisations/conversations';
import {
  type BreadcrumbItem,
  type Conversation,
  type Dataset,
  type Organisation,
  type PaginatedData,
  type SharedData,
} from '@/types';
import { Head, Link, router, usePage } from '@inertiajs/react';
import { Search } from 'lucide-react';
import { useState } from 'react';

interface IndexProps {
  organisation: Organisation;
  conversations: PaginatedData<Conversation>;
  datasets: Dataset[];
}

export default function ConversationsIndex({
  organisation,
  conversations,
  datasets,
}: IndexProps) {
  const { auth } = usePage<SharedData>().props;
  const [search, setSearch] = useState('');
  const [isDialogOpen, setIsDialogOpen] = useState(false);

  const handleDelete = () => {
    router.reload({ only: ['conversations'] });
  };

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
      title: 'Chats',
      href: conversationsIndex.url({ organisation: organisation.uuid }),
    },
  ];

  return (
    <AppLayout breadcrumbs={breadcrumbs}>
      <Head title={`Chats - ${organisation.name}`} />
      <div className="flex h-full flex-1 flex-col overflow-hidden rounded-xl p-4">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold">Chats</h1>
          <Button onClick={() => setIsDialogOpen(true)}>+ New chat</Button>
        </div>

        <NewConversationDialog
          organisation={organisation}
          datasets={datasets}
          open={isDialogOpen}
          onOpenChange={setIsDialogOpen}
        />

        <div className="relative mb-4">
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search your chats..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>

        <div className="mb-4 flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {conversations.total} chat{conversations.total !== 1 ? 's' : ''}{' '}
            with {organisation.name}
          </span>
          <button className="hover:text-foreground">Select</button>
        </div>

        {conversations.data.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-sidebar-border/70 p-12 text-center dark:border-sidebar-border">
            <p className="text-muted-foreground">
              {search
                ? 'No conversations found matching your search.'
                : 'No conversations found. Start a conversation from a dataset to get started.'}
            </p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">
            <div className="space-y-0">
              {conversations.data.map((conversation, index) => (
                <div key={conversation.id}>
                  <ConversationCard
                    conversation={conversation}
                    organisation={organisation}
                    currentUser={auth.user}
                    onDelete={handleDelete}
                  />
                  {index < conversations.data.length - 1 && (
                    <div className="border-t border-sidebar-border/70 dark:border-sidebar-border" />
                  )}
                </div>
              ))}
            </div>

            {conversations.last_page > 1 && (
              <div className="mt-4 py-4">
                <div className="-mb-1 flex flex-wrap">
                  {conversations.links.map((link, key) =>
                    link.url === null ? (
                      <div
                        key={key}
                        className="mr-1 mb-1 rounded border px-4 py-3 text-sm leading-4 text-gray-400"
                        dangerouslySetInnerHTML={{ __html: link.label }}
                      />
                    ) : (
                      <Link
                        key={`link-${key}`}
                        href={link.url}
                        className={`mr-1 mb-1 rounded border px-4 py-3 text-sm leading-4 hover:bg-white focus:border-indigo-500 focus:text-indigo-500 dark:hover:bg-neutral-900 ${link.active ? 'bg-white dark:bg-neutral-900' : ''}`}
                      >
                        <span
                          dangerouslySetInnerHTML={{ __html: link.label }}
                        />
                      </Link>
                    ),
                  )}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </AppLayout>
  );
}
