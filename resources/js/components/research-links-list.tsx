import { MarkdownContent } from '@/components/markdown-content';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import { Spinner } from '@/components/ui/spinner';
import { type ResearchLink } from '@/types';
import { CheckCircle2, ChevronDown, Clock, ExternalLink, XCircle } from 'lucide-react';
import { useState } from 'react';

interface ResearchLinksListProps {
  links: ResearchLink[];
  showContainer?: boolean;
  isProcessing?: boolean;
}

function ResearchLinkItem({ link }: { link: ResearchLink }) {
  const [isOpen, setIsOpen] = useState(false);

  const getStatusIcon = () => {
    if (link.status === 'completed') {
      return <CheckCircle2 className="size-5 text-green-600 dark:text-green-500" />;
    }
    if (link.status === 'pending') {
      return <Clock className="size-5 text-yellow-600 dark:text-yellow-500" />;
    }
    if (link.status === 'failed') {
      return <XCircle className="size-5 text-red-600 dark:text-red-500" />;
    }
    return null;
  };

  return (
    <Collapsible
      open={isOpen}
      onOpenChange={setIsOpen}
      className="rounded-lg border border-border"
    >
      <CollapsibleTrigger className="flex w-full items-center justify-between gap-2 p-4 text-left hover:bg-accent/50 transition-colors">
        <div className="flex flex-1 items-center gap-3 min-w-0">
          {getStatusIcon()}
          <a
            href={link.url}
            target="_blank"
            rel="noopener noreferrer"
            onClick={(e) => e.stopPropagation()}
            className="flex items-center gap-2 text-blue-600 underline hover:text-blue-700 dark:text-blue-400 dark:hover:text-blue-300 flex-1 min-w-0"
          >
            <span className="line-clamp-1 truncate">{link.url}</span>
            <ExternalLink className="size-4 shrink-0" />
          </a>
        </div>
        <ChevronDown
          className={`size-4 shrink-0 text-muted-foreground transition-transform ${
            isOpen ? 'rotate-180' : ''
          }`}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="px-4 pb-4">
        {link.summary ? (
          <div className="mt-2 pt-2 border-t">
            <MarkdownContent content={link.summary} />
          </div>
        ) : link.status === 'pending' ? (
          <div className="mt-2 pt-2 border-t text-sm text-muted-foreground">
            Content is being processed...
          </div>
        ) : link.status === 'failed' ? (
          <div className="mt-2 pt-2 border-t text-sm text-red-600 dark:text-red-500">
            Failed to process this link
          </div>
        ) : null}
      </CollapsibleContent>
    </Collapsible>
  );
}

export function ResearchLinksList({
  links,
  showContainer = true,
  isProcessing = false,
}: ResearchLinksListProps) {
  if (!links || links.length === 0) {
    return null;
  }

  const content = (
    <>
      {showContainer && (
        <div className="mb-4 flex items-center gap-2">
          <h2 className="text-lg font-semibold">Research Links</h2>
          {isProcessing && (
            <Spinner className="size-4 text-muted-foreground" />
          )}
        </div>
      )}
      <div className="space-y-2">
        {links.map((link) => (
          <ResearchLinkItem key={link.id} link={link} />
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
