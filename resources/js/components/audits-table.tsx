import { Badge } from '@/components/ui/badge';
import { show as showAudit } from '@/routes/organisations/audits/index';
import { type Audit, type Organisation, type PaginatedData } from '@/types';
import { Link } from '@inertiajs/react';

interface AuditsTableProps {
  audits: PaginatedData<Audit>;
  organisation: Organisation;
}

export default function AuditsTable({
  audits,
  organisation,
}: AuditsTableProps) {
  const formatDate = (dateString?: string): string => {
    if (!dateString) {
      return 'N/A';
    }
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  const getStatusBadge = (status: Audit['status']) => {
    switch (status) {
      case 'completed':
        return (
          <Badge variant="default" className="bg-green-600 dark:bg-green-500">
            Completed
          </Badge>
        );
      case 'in_progress':
        return <Badge variant="secondary">In Progress</Badge>;
      case 'failed':
        return <Badge variant="destructive">Failed</Badge>;
      case 'pending':
      default:
        return <Badge variant="secondary">Pending</Badge>;
    }
  };

  return (
    <div className="space-y-4">
      {audits.data.length === 0 ? (
        <div className="rounded-lg border border-sidebar-border/70 p-8 text-center dark:border-sidebar-border">
          <p className="text-muted-foreground">
            No audits found. Create your first audit to get started.
          </p>
        </div>
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-sidebar-border/70 dark:border-sidebar-border">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    Website URL
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    User
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    Status
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium">
                    Created At
                  </th>
                </tr>
              </thead>
              <tbody>
                {audits.data.map((audit) => (
                  <tr
                    key={audit.id}
                    className="border-t border-sidebar-border/70 dark:border-sidebar-border"
                  >
                    <td className="px-4 py-3 text-sm">
                      <div className="font-medium">
                        <Link
                          href={showAudit.url({
                            organisation: organisation.uuid,
                            audit: { id: audit.id },
                          })}
                          className="text-primary hover:underline"
                        >
                          {audit.website_url}
                        </Link>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {audit.user?.name || 'N/A'}
                    </td>
                    <td className="px-4 py-3 text-sm">
                      {getStatusBadge(audit.status)}
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {formatDate(audit.created_at)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {audits.last_page > 1 && (
            <>
              <div className="text-sm text-muted-foreground">
                Showing {audits.from || 0} to {audits.to || 0} of {audits.total}{' '}
                audits
              </div>
              <div className="py-4">
                <div className="-mb-1 flex flex-wrap">
                  {audits.links.map((link, key) =>
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
            </>
          )}
        </>
      )}
    </div>
  );
}
