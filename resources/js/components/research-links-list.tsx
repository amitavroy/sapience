import { MarkdownContent } from '@/components/markdown-content';
import { type ResearchLink } from '@/types';
import { ExternalLink } from 'lucide-react';

interface ResearchLinksListProps {
  links: ResearchLink[];
  showContainer?: boolean;
}

export function ResearchLinksList({
  links,
  showContainer = true,
}: ResearchLinksListProps) {
  if (!links || links.length === 0) {
    return null;
  }

  const content = (
    <>
      {showContainer && (
        <h2 className="mb-4 text-lg font-semibold">Research Links</h2>
      )}
      <div className="space-y-4">
        {links.map((link) => (
          <div key={link.id} className="rounded-lg border border-border p-4">
            <div className="mb-2 flex items-start justify-between gap-2">
              <a
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
                className="flex items-center gap-2 text-blue-600 underline hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300"
              >
                <span className="line-clamp-2">{link.url}</span>
                <ExternalLink className="size-4 shrink-0" />
              </a>
            </div>
            {link.summary && (
              <div className="mt-2">
                <MarkdownContent content={link.summary} />
              </div>
            )}
            <div className="mt-2 flex items-center gap-2 text-xs text-muted-foreground">
              <span
                className={`rounded px-2 py-1 ${
                  link.status === 'completed'
                    ? 'bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400'
                    : link.status === 'failed'
                      ? 'bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400'
                      : 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400'
                }`}
              >
                {link.status}
              </span>
            </div>
          </div>
        ))}
      </div>
    </>
  );

  if (!showContainer) {
    return <>{content}</>;
  }

  return (
    <div className="rounded-xl border border-sidebar-border/70 p-6 dark:border-sidebar-border">
      {content}
    </div>
  );
}
