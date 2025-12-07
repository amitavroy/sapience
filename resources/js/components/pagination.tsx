import { PaginatedData } from '@/types';
import { Link } from '@inertiajs/react';

interface PaginationProps<T> {
  links: PaginatedData<T>['links'];
}

export default function Pagination<T>({ links }: PaginationProps<T>) {
  if (links.length <= 3) return null;

  return (
    <div className="py-4">
      <div className="-mb-1 flex flex-wrap">
        {links.map((link, key) =>
          link.url === null ? (
            <div
              key={key}
              className="mr-1 mb-1 rounded border px-4 py-3 text-sm leading-4 text-gray-400"
              dangerouslySetInnerHTML={{ __html: link.label }}
            />
          ) : (
            <Link
              key={`link-${key}`}
              className={`mr-1 mb-1 rounded border px-4 py-3 text-sm leading-4 hover:bg-white focus:border-indigo-500 focus:text-indigo-500 dark:hover:bg-neutral-900 ${link.active ? 'bg-white dark:bg-neutral-900' : ''}`}
              href={link.url}
            >
              <span dangerouslySetInnerHTML={{ __html: link.label }} />
            </Link>
          ),
        )}
      </div>
    </div>
  );
}
