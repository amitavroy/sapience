import { ResearchCard } from '@/components/research-card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import AppLayout from '@/layouts/app-layout';
import { dashboard } from '@/routes/organisations';
import {
  create as createResearch,
  index as researchIndex,
} from '@/routes/organisations/research';
import {
  type BreadcrumbItem,
  type Organisation,
  type PaginatedData,
  type Research,
  type SharedData,
} from '@/types';
import { Head, Link, router, usePage } from '@inertiajs/react';
import { Search } from 'lucide-react';
import { useState } from 'react';

interface IndexProps {
  organisation: Organisation;
  researches: PaginatedData<Research>;
}

export default function ResearchIndex({
  organisation,
  researches,
}: IndexProps) {
  const { auth } = usePage<SharedData>().props;
  const [search, setSearch] = useState('');

  const handleDelete = () => {
    router.reload({ only: ['researches'] });
  };

  const filteredResearches = researches.data.filter((research) => {
    if (!search) {
      return true;
    }
    const searchLower = search.toLowerCase();
    return (
      research.query.toLowerCase().includes(searchLower) ||
      research.description?.toLowerCase().includes(searchLower)
    );
  });

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
      title: 'Research',
      href: researchIndex.url({ organisation: organisation.uuid }),
    },
  ];

  return (
    <AppLayout breadcrumbs={breadcrumbs}>
      <Head title={`Research - ${organisation.name}`} />
      <div className="flex h-full flex-1 flex-col overflow-hidden rounded-xl p-4">
        <div className="mb-6 flex items-center justify-between">
          <h1 className="text-2xl font-bold">Research</h1>
          <Link href={createResearch(organisation.uuid).url}>
            <Button>+ New Research</Button>
          </Link>
        </div>

        <div className="relative mb-4">
          <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            type="text"
            placeholder="Search research..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="pl-9"
          />
        </div>

        <div className="mb-4 flex items-center justify-between text-sm text-muted-foreground">
          <span>
            {researches.total} research{researches.total !== 1 ? 'es' : ''} in{' '}
            {organisation.name}
          </span>
        </div>

        {filteredResearches.length === 0 ? (
          <div className="flex flex-col items-center justify-center rounded-xl border border-sidebar-border/70 p-12 text-center dark:border-sidebar-border">
            <p className="text-muted-foreground">
              {search
                ? 'No research found matching your search.'
                : 'No research found. Create a new research to get started.'}
            </p>
          </div>
        ) : (
          <div className="flex-1 overflow-y-auto">
            <div className="space-y-0">
              {filteredResearches.map((research, index) => (
                <div key={research.id}>
                  <ResearchCard
                    research={research}
                    organisation={organisation}
                    currentUser={auth.user}
                    onDelete={handleDelete}
                  />
                  {index < filteredResearches.length - 1 && (
                    <div className="border-t border-sidebar-border/70 dark:border-sidebar-border" />
                  )}
                </div>
              ))}
            </div>

            {researches.last_page > 1 && (
              <div className="mt-4 py-4">
                <div className="-mb-1 flex flex-wrap">
                  {researches.links.map((link, key) =>
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
