import { Button } from '@/components/ui/button';
import { Spinner } from '@/components/ui/spinner';
import { formatFileSize } from '@/lib/utils';
import { type Dataset, type Organisation } from '@/types';
import { Upload, X } from 'lucide-react';
import { useCallback, useState } from 'react';

interface FileUploadProps {
  organisation: Organisation;
  dataset: Dataset;
  onUploadComplete?: () => void;
  onFilesValidated?: (files: File[]) => void;
}

interface FileWithProgress {
  file: File;
  progress: number;
  status: 'pending' | 'uploading' | 'completed' | 'error';
  error?: string;
  fileId?: number;
}

export default function FileUpload({
  organisation,
  dataset,
  onUploadComplete,
  onFilesValidated,
}: FileUploadProps) {
  const [files, setFiles] = useState<FileWithProgress[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);

  const handleFiles = useCallback((fileList: FileList | null) => {
    if (!fileList) {
      return;
    }

    const newFiles: FileWithProgress[] = Array.from(fileList).map((file) => ({
      file,
      progress: 0,
      status: 'pending' as const,
    }));

    setFiles((prev) => [...prev, ...newFiles]);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      handleFiles(e.dataTransfer.files);
    },
    [handleFiles],
  );

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const uploadFileToS3 = async (
    file: File,
    uploadUrl: string,
    headers: Record<string, string>,
    onProgress: (progress: number) => void,
  ): Promise<void> => {
    return new Promise((resolve, reject) => {
      const xhr = new XMLHttpRequest();

      xhr.upload.addEventListener('progress', (e) => {
        if (e.lengthComputable) {
          const progress = Math.round((e.loaded / e.total) * 100);
          onProgress(progress);
        }
      });

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve();
        } else {
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      });

      xhr.addEventListener('error', () => {
        reject(new Error('Upload failed'));
      });

      xhr.open('PUT', uploadUrl);

      // Set headers (filter out unsafe headers that browsers don't allow)
      const unsafeHeaders = [
        'host',
        'connection',
        'keep-alive',
        'transfer-encoding',
        'upgrade',
        'content-length', // Browser sets this automatically
      ];

      Object.entries(headers).forEach(([key, value]) => {
        const lowerKey = key.toLowerCase();
        if (!unsafeHeaders.includes(lowerKey)) {
          xhr.setRequestHeader(key, value);
        }
      });

      xhr.send(file);
    });
  };

  const handleUpload = async () => {
    if (files.length === 0 || isProcessing) {
      return;
    }

    setIsProcessing(true);

    try {
      // Step 1: Request upload URLs from backend
      const response = await fetch(
        `/organisations/${organisation.uuid}/datasets/${dataset.uuid}/files/request-upload`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRF-TOKEN':
              document
                .querySelector('meta[name="csrf-token"]')
                ?.getAttribute('content') || '',
            Accept: 'application/json',
          },
          body: JSON.stringify({
            files: files.map((f) => ({
              original_filename: f.file.name,
              file_size: f.file.size,
              mime_type: f.file.type || 'application/octet-stream', // Fallback for empty MIME types
            })),
          }),
        },
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        const errorMessage =
          errorData.message ||
          (errorData.errors
            ? Object.values(errorData.errors).flat().join(', ')
            : 'Failed to request upload URLs');
        throw new Error(errorMessage);
      }

      const { upload_data } = await response.json();

      // Step 2: Upload files to S3
      const uploadPromises = upload_data.map(
        async (
          uploadInfo: {
            file_id: number;
            upload_url: string;
            headers: Record<string, string>;
          },
          index: number,
        ): Promise<{ file_id: number; success: boolean }> => {
          const fileWithProgress = files[index];
          setFiles((prev) =>
            prev.map((f, i) =>
              i === index
                ? { ...f, status: 'uploading', fileId: uploadInfo.file_id }
                : f,
            ),
          );

          try {
            await uploadFileToS3(
              fileWithProgress.file,
              uploadInfo.upload_url,
              uploadInfo.headers,
              (progress) => {
                setFiles((prev) =>
                  prev.map((f, i) => (i === index ? { ...f, progress } : f)),
                );
              },
            );

            setFiles((prev) =>
              prev.map((f, i) =>
                i === index ? { ...f, status: 'completed', progress: 100 } : f,
              ),
            );

            return { file_id: uploadInfo.file_id, success: true };
          } catch (error) {
            setFiles((prev) =>
              prev.map((f, i) =>
                i === index
                  ? {
                      ...f,
                      status: 'error',
                      error:
                        error instanceof Error
                          ? error.message
                          : 'Upload failed',
                    }
                  : f,
              ),
            );
            return { file_id: uploadInfo.file_id, success: false };
          }
        },
      );

      const uploadResults = await Promise.allSettled(uploadPromises);

      // Step 3: Complete upload validation
      const completedFileIds = uploadResults
        .filter(
          (result) => result.status === 'fulfilled' && result.value.success,
        )
        .map((result) =>
          result.status === 'fulfilled' ? result.value.file_id : 0,
        )
        .filter((id) => id > 0);

      console.log('Completed file IDs to validate:', completedFileIds);

      if (completedFileIds.length > 0) {
        try {
          console.log('Calling complete endpoint...');
          const completeResponse = await fetch(
            `/organisations/${organisation.uuid}/datasets/${dataset.uuid}/files/complete`,
            {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'X-CSRF-TOKEN':
                  document
                    .querySelector('meta[name="csrf-token"]')
                    ?.getAttribute('content') || '',
                Accept: 'application/json',
              },
              body: JSON.stringify({
                file_ids: completedFileIds,
              }),
            },
          );

          console.log('Complete response status:', completeResponse.status);

          if (!completeResponse.ok) {
            const errorData = await completeResponse.json().catch(() => ({}));
            console.error('Complete upload error:', errorData);
            throw new Error(
              errorData.message || 'Failed to complete upload validation',
            );
          }

          const result = await completeResponse.json();
          console.log('Files validated successfully:', result);

          // Add validated files to the table
          if (result.files && result.files.length > 0) {
            onFilesValidated?.(result.files);
          }
        } catch (error) {
          console.error('Error completing upload validation:', error);
          // Don't throw - allow the upload to be considered successful
          // The files will remain in pending status and can be validated later
        }
      } else {
        console.warn('No files completed successfully, skipping validation');
      }

      // Clear files
      setFiles([]);
      onUploadComplete?.();
    } catch (error) {
      console.error('Upload error:', error);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="space-y-4">
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        className={`rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
          isDragging
            ? 'border-primary bg-primary/5'
            : 'border-sidebar-border/70 dark:border-sidebar-border'
        }`}
      >
        <Upload className="mx-auto mb-4 size-8 text-muted-foreground" />
        <p className="mb-2 text-sm font-medium">
          Drag and drop files here, or click to select
        </p>
        <p className="mb-4 text-xs text-muted-foreground">
          You can upload multiple files at once
        </p>
        <label htmlFor="file-upload">
          <Button type="button" variant="outline" asChild>
            <span>Select Files</span>
          </Button>
          <input
            id="file-upload"
            type="file"
            multiple
            className="hidden"
            onChange={(e) => handleFiles(e.target.files)}
          />
        </label>
      </div>

      {files.length > 0 && (
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-medium">
              Selected Files ({files.length})
            </h3>
            <Button onClick={handleUpload} disabled={isProcessing} size="sm">
              {isProcessing && <Spinner />}
              Upload Files
            </Button>
          </div>
          <div className="space-y-2">
            {files.map((fileWithProgress, index) => (
              <div
                key={index}
                className="flex items-center gap-4 rounded-lg border border-sidebar-border/70 p-3 dark:border-sidebar-border"
              >
                <div className="flex-1">
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-medium">
                      {fileWithProgress.file.name}
                    </p>
                    <button
                      type="button"
                      onClick={() => removeFile(index)}
                      className="text-muted-foreground hover:text-foreground"
                      disabled={isProcessing}
                    >
                      <X className="size-4" />
                    </button>
                  </div>
                  <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                    <span>{formatFileSize(fileWithProgress.file.size)}</span>
                    <span>•</span>
                    <span>{fileWithProgress.file.type || 'Unknown type'}</span>
                    {fileWithProgress.status === 'uploading' && (
                      <>
                        <span>•</span>
                        <span>{fileWithProgress.progress}%</span>
                      </>
                    )}
                  </div>
                  {fileWithProgress.status === 'uploading' && (
                    <div className="mt-2 h-1 w-full overflow-hidden rounded-full bg-secondary">
                      <div
                        className="h-full bg-primary transition-all"
                        style={{ width: `${fileWithProgress.progress}%` }}
                      />
                    </div>
                  )}
                  {fileWithProgress.status === 'error' && (
                    <p className="mt-1 text-xs text-destructive">
                      {fileWithProgress.error}
                    </p>
                  )}
                  {fileWithProgress.status === 'completed' && (
                    <p className="mt-1 text-xs text-green-600 dark:text-green-400">
                      Uploaded successfully
                    </p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
