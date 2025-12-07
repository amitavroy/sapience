<?php

namespace App\Actions;

use App\Enums\FileStatus;
use App\Models\Dataset;
use App\Models\File;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Facades\Storage;

class DeleteFileAction
{
    /**
     * Delete a file from database and S3 if applicable.
     */
    public function execute(File $file, Dataset $dataset): void
    {
        // Delete from S3 if file was uploaded (completed or invalid status)
        // Invalid files should have been deleted during validation, but we'll try anyway
        if ($file->status === FileStatus::Completed || $file->status === FileStatus::Invalid) {
            $s3Path = "datasets/{$dataset->id}/files/{$file->filename}";

            try {
                $disk = Storage::disk('s3');

                // Check if file exists first
                $exists = $disk->exists($s3Path);

                if ($exists) {
                    $disk->delete($s3Path);
                }
            } catch (\Exception $e) {
                // Continue with database deletion even if S3 deletion fails
            }
        }

        // Detach from dataset and delete the file record in a transaction
        DB::transaction(function () use ($dataset, $file) {
            // Detach from dataset (this won't delete the file record due to cascade)
            $dataset->files()->detach($file->id);

            // Delete the file record
            $file->delete();
        });
    }
}
