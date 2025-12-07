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
import { Input } from '@/components/ui/input';
import { Spinner } from '@/components/ui/spinner';
import { formatFileSize } from '@/lib/utils';
import {
  type Dataset,
  type File,
  type Organisation,
  type PaginatedFiles,
} from '@/types';
import { ChevronLeft, ChevronRight, Search, Trash2 } from 'lucide-react';
import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react';

interface FilesTableProps {
  organisation: Organisation;
  dataset: Dataset;
}

export interface FilesTableRef {
  addFiles: (newFiles: File[]) => void;
  refresh: () => void;
}

const FilesTable = forwardRef<FilesTableRef, FilesTableProps>(
  function FilesTable({ organisation, dataset }, ref) {
    const [files, setFiles] = useState<PaginatedFiles | null>(null);
    const [loading, setLoading] = useState(true);
    const [search, setSearch] = useState('');
    const [currentPage, setCurrentPage] = useState(1);
    const [searchDebounce, setSearchDebounce] = useState<NodeJS.Timeout | null>(
      null,
    );
    const [deletingFileId, setDeletingFileId] = useState<number | null>(null);
    const fetchFilesRef = useRef<
      ((page: number, searchQuery: string) => Promise<void>) | null
    >(null);

    const fetchFiles = useCallback(
      async (page: number = 1, searchQuery: string = '') => {
        setLoading(true);
        try {
          const params = new URLSearchParams({
            page: page.toString(),
            per_page: '15',
          });

          if (searchQuery) {
            params.append('search', searchQuery);
          }

          const response = await fetch(
            `/organisations/${organisation.uuid}/datasets/${dataset.uuid}/files?${params.toString()}`,
            {
              headers: {
                Accept: 'application/json',
                'X-CSRF-TOKEN':
                  document
                    .querySelector('meta[name="csrf-token"]')
                    ?.getAttribute('content') || '',
              },
            },
          );

          if (!response.ok) {
            throw new Error('Failed to fetch files');
          }

          const data: PaginatedFiles = await response.json();
          setFiles(data);
        } catch (error) {
          console.error('Error fetching files:', error);
        } finally {
          setLoading(false);
        }
      },
      [organisation.uuid, dataset.uuid],
    );

    fetchFilesRef.current = fetchFiles;

    useImperativeHandle(ref, () => ({
      addFiles: (newFiles: File[]) => {
        setFiles((prev) => {
          if (!prev) {
            return null;
          }
          return {
            ...prev,
            data: [...newFiles, ...prev.data],
            total: prev.total + newFiles.length,
          };
        });
      },
      refresh: () => {
        fetchFiles(currentPage, search);
      },
    }));

    useEffect(() => {
      fetchFiles(currentPage, search);
    }, [currentPage, fetchFiles]);

    useEffect(() => {
      // Debounce search
      if (searchDebounce) {
        clearTimeout(searchDebounce);
      }

      const timeout = setTimeout(() => {
        setCurrentPage(1);
        fetchFiles(1, search);
      }, 500);

      setSearchDebounce(timeout);

      return () => {
        if (timeout) {
          clearTimeout(timeout);
        }
      };
    }, [search, fetchFiles]);

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

    const getStatusBadge = (status: File['status']) => {
      switch (status) {
        case 'completed':
          return (
            <Badge variant="default" className="bg-green-600 dark:bg-green-500">
              Completed
            </Badge>
          );
        case 'pending':
          return <Badge variant="secondary">Pending</Badge>;
        case 'invalid':
          return <Badge variant="destructive">Invalid</Badge>;
        default:
          return <Badge variant="secondary">{status}</Badge>;
      }
    };

    const handleDelete = async (file: File) => {
      setDeletingFileId(file.id);
      try {
        const response = await fetch(
          `/organisations/${organisation.uuid}/datasets/${dataset.uuid}/files/${file.uuid}`,
          {
            method: 'DELETE',
            headers: {
              Accept: 'application/json',
              'X-CSRF-TOKEN':
                document
                  .querySelector('meta[name="csrf-token"]')
                  ?.getAttribute('content') || '',
            },
          },
        );

        if (!response.ok) {
          throw new Error('Failed to delete file');
        }

        // Refresh the file list
        await fetchFiles(currentPage, search);
      } catch (error) {
        console.error('Error deleting file:', error);
        alert('Failed to delete file. Please try again.');
      } finally {
        setDeletingFileId(null);
      }
    };

    if (loading && !files) {
      return (
        <div className="flex items-center justify-center p-8">
          <Spinner />
        </div>
      );
    }

    return (
      <div className="space-y-4">
        <div className="flex items-center gap-4">
          <div className="relative flex-1">
            <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              type="text"
              placeholder="Search files by name..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9"
            />
          </div>
        </div>

        {files && files.data.length === 0 ? (
          <div className="rounded-lg border border-sidebar-border/70 p-8 text-center dark:border-sidebar-border">
            <p className="text-muted-foreground">
              {search
                ? 'No files found matching your search.'
                : 'No files uploaded yet.'}
            </p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto rounded-lg border border-sidebar-border/70 dark:border-sidebar-border">
              <table className="w-full">
                <thead className="bg-muted/50">
                  <tr>
                    <th className="px-4 py-3 text-left text-sm font-medium">
                      Filename
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium">
                      Size
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium">
                      Type
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium">
                      Status
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium">
                      Uploaded By
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium">
                      Uploaded At
                    </th>
                    <th className="px-4 py-3 text-left text-sm font-medium">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {files?.data.map((file) => (
                    <tr
                      key={file.id}
                      className="border-t border-sidebar-border/70 dark:border-sidebar-border"
                    >
                      <td className="px-4 py-3 text-sm">
                        <div className="font-medium">
                          {file.original_filename}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {formatFileSize(file.file_size)}
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {file.mime_type || 'Unknown'}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        {getStatusBadge(file.status)}
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {file.user.name}
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {formatDate(file.created_at)}
                      </td>
                      <td className="px-4 py-3 text-sm">
                        <Dialog>
                          <DialogTrigger asChild>
                            <Button
                              variant="ghost"
                              size="icon"
                              className="size-8 text-muted-foreground hover:text-destructive"
                              disabled={deletingFileId === file.id}
                            >
                              {deletingFileId === file.id ? (
                                <Spinner />
                              ) : (
                                <Trash2 className="size-4" />
                              )}
                            </Button>
                          </DialogTrigger>
                          <DialogContent>
                            <DialogTitle>Delete File</DialogTitle>
                            <DialogDescription>
                              Are you sure you want to delete "
                              {file.original_filename}"?
                              {file.status === 'completed' && (
                                <span className="mt-2 block">
                                  This will permanently delete the file from
                                  storage and cannot be undone.
                                </span>
                              )}
                              {file.status === 'pending' && (
                                <span className="mt-2 block">
                                  This will remove the file entry. The file has
                                  not been uploaded yet.
                                </span>
                              )}
                            </DialogDescription>
                            <DialogFooter className="gap-2">
                              <DialogClose asChild>
                                <Button variant="secondary">Cancel</Button>
                              </DialogClose>
                              <Button
                                variant="destructive"
                                onClick={() => handleDelete(file)}
                                disabled={deletingFileId === file.id}
                              >
                                {deletingFileId === file.id ? (
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
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {files && files.last_page > 1 && (
              <div className="flex items-center justify-between">
                <div className="text-sm text-muted-foreground">
                  Showing {files.data.length} of {files.total} files
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                    disabled={currentPage === 1 || loading}
                  >
                    <ChevronLeft className="size-4" />
                    Previous
                  </Button>
                  <div className="text-sm text-muted-foreground">
                    Page {files.current_page} of {files.last_page}
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() =>
                      setCurrentPage((p) => Math.min(files.last_page, p + 1))
                    }
                    disabled={currentPage === files.last_page || loading}
                  >
                    Next
                    <ChevronRight className="size-4" />
                  </Button>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    );
  },
);

export default FilesTable;
