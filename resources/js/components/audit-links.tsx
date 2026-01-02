import { MarkdownContent } from '@/components/markdown-content';
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from '@/components/ui/collapsible';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { cn } from '@/lib/utils';
import { type AuditLink } from '@/types';
import { ChevronDown } from 'lucide-react';
import { useState } from 'react';

interface AuditLinksProps {
  auditLinks: AuditLink[];
}

export function AuditLinks({ auditLinks }: AuditLinksProps) {
  const [openIndex, setOpenIndex] = useState<number | null>(null);

  if (!auditLinks || auditLinks.length === 0) {
    return (
      <div className="rounded-xl border border-sidebar-border/70 p-8 text-center dark:border-sidebar-border">
        <p className="text-muted-foreground">No audit links available yet.</p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {auditLinks.map((link, index) => {
        const isOpen = openIndex === index;

        return (
          <Collapsible
            key={link.id}
            open={isOpen}
            onOpenChange={(open) => {
              setOpenIndex(open ? index : null);
            }}
          >
            <div className="rounded-xl border border-sidebar-border/70 dark:border-sidebar-border">
              <CollapsibleTrigger className="flex w-full items-center justify-between p-4 text-left transition-colors hover:bg-muted/50">
                <div className="min-w-0 flex-1">
                  <h3 className="truncate font-semibold">
                    <a
                      href={link.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      onClick={(e) => e.stopPropagation()}
                      className="text-primary hover:underline"
                    >
                      {link.title || link.url}
                    </a>
                  </h3>
                  {link.title && (
                    <p className="mt-1 truncate text-sm text-muted-foreground">
                      <a
                        href={link.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        onClick={(e) => e.stopPropagation()}
                        className="text-muted-foreground hover:text-foreground hover:underline"
                      >
                        {link.url}
                      </a>
                    </p>
                  )}
                </div>
                <ChevronDown
                  className={cn(
                    'ml-4 h-4 w-4 shrink-0 text-muted-foreground transition-transform',
                    isOpen && 'rotate-180 transform',
                  )}
                />
              </CollapsibleTrigger>
              <CollapsibleContent>
                <div className="border-t border-sidebar-border/70 p-4 dark:border-sidebar-border">
                  <Tabs defaultValue="summary">
                    <TabsList>
                      <TabsTrigger value="summary">Summary</TabsTrigger>
                      <TabsTrigger value="content">Content</TabsTrigger>
                    </TabsList>
                    <TabsContent value="summary" className="mt-4">
                      {link.summary ? (
                        <div className="overflow-x-auto">
                          <MarkdownContent content={link.summary} />
                        </div>
                      ) : (
                        <p className="text-muted-foreground">
                          No summary available yet.
                        </p>
                      )}
                    </TabsContent>
                    <TabsContent value="content" className="mt-4">
                      {link.content ? (
                        <div className="overflow-x-auto">
                          <MarkdownContent content={link.content} />
                        </div>
                      ) : (
                        <p className="text-muted-foreground">
                          No content available yet.
                        </p>
                      )}
                    </TabsContent>
                  </Tabs>
                </div>
              </CollapsibleContent>
            </div>
          </Collapsible>
        );
      })}
    </div>
  );
}
