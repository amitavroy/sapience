<?php

namespace App\Actions;

use App\Models\Dataset;
use App\Services\TypesenseService;
use App\Services\UtilService;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Storage;

class DeleteDatasetAction
{
    public function __construct(
        private TypesenseService $typesenseService
    ) {}

    /**
     * Delete a dataset and optionally its files and conversations.
     *
     * @throws \RuntimeException if conversations exist and deleteConversations is false
     */
    public function execute(Dataset $dataset, bool $deleteFiles, bool $deleteConversations): void
    {
        // Check if conversations exist and user doesn't want to delete them
        if (! $deleteConversations && $dataset->conversations()->exists()) {
            throw new \RuntimeException(
                'Cannot delete dataset: conversations exist. Please delete conversations first or select "Delete associated conversations".'
            );
        }

        DB::transaction(function () use ($dataset, $deleteFiles, $deleteConversations) {
            // Always delete Typesense collection
            try {
                $this->typesenseService->deleteCollection(
                    $dataset->organisation_id,
                    $dataset->id
                );
            } catch (\Exception $e) {
                Log::error('Failed to delete Typesense collection during dataset deletion', [
                    'dataset_id' => $dataset->id,
                    'organisation_id' => $dataset->organisation_id,
                    'error' => $e->getMessage(),
                ]);
                // Continue with deletion even if Typesense deletion fails
            }

            // Conditionally delete files
            if ($deleteFiles) {
                $this->deleteFiles($dataset);
            }

            // Conditionally delete conversations
            if ($deleteConversations) {
                $this->deleteConversations($dataset);
            }

            // Delete the dataset record (this will cascade delete pivot table entries)
            $dataset->delete();
        });
    }

    /**
     * Delete files that belong exclusively to this dataset.
     */
    private function deleteFiles(Dataset $dataset): void
    {
        $files = $dataset->files()->get();
        $diskName = env('FILESYSTEM_UPLOADS_DISK', 'minio');

        foreach ($files as $file) {
            // Check if file belongs to other datasets
            $otherDatasets = $file->datasets()
                ->where('datasets.id', '!=', $dataset->id)
                ->count();

            if ($otherDatasets === 0) {
                // File belongs exclusively to this dataset - delete from storage and database
                try {
                    $s3Path = UtilService::getFileS3Path($dataset, $file);

                    if (Storage::disk($diskName)->exists($s3Path)) {
                        Storage::disk($diskName)->delete($s3Path);
                    }
                } catch (\Exception $e) {
                    Log::warning('Failed to delete file from storage during dataset deletion', [
                        'file_id' => $file->id,
                        'dataset_id' => $dataset->id,
                        'disk' => $diskName,
                        's3_path' => $s3Path ?? 'unknown',
                        'error' => $e->getMessage(),
                    ]);
                    // Continue with database deletion even if storage deletion fails
                }

                // Delete the file record
                $file->delete();
            } else {
                // File belongs to other datasets - just detach from this dataset
                $dataset->files()->detach($file->id);
            }
        }
    }

    /**
     * Delete all conversations associated with the dataset.
     */
    private function deleteConversations(Dataset $dataset): void
    {
        $conversations = $dataset->conversations()->get();

        foreach ($conversations as $conversation) {
            // Delete all messages associated with the conversation
            $conversation->messages()->delete();

            // Delete the conversation
            $conversation->delete();
        }
    }
}
