<?php

namespace App\Actions;

use App\Enums\FileStatus;
use App\Jobs\ProcessFileForVectorStore;
use App\Models\Dataset;
use App\Models\File;
use App\Services\UtilService;
use Illuminate\Support\Facades\Storage;

class CompleteFileUploadAction
{
    /**
     * Complete file upload validation for multiple files.
     *
     * @param  array<int, int>  $fileIds
     * @return array<int, File>
     */
    public function execute(array $fileIds, Dataset $dataset): array
    {
        $files = File::whereIn('id', $fileIds)
            ->whereHas('datasets', function ($query) use ($dataset) {
                $query->where('datasets.id', $dataset->id);
            })
            ->with('user')
            ->get();

        $validatedFiles = [];
        $disk = 's3';

        foreach ($files as $file) {
            $s3Path = UtilService::getFileS3Path($dataset, $file);

            try {
                // Check if file exists in S3
                if (! Storage::disk($disk)->exists($s3Path)) {
                    $file->update(['status' => FileStatus::Invalid->value]);

                    continue;
                }

                // Get file size from S3
                $actualSize = Storage::disk($disk)->size($s3Path);
                $expectedSize = (int) $file->file_size;

                // Download first 512 bytes to validate file is readable
                $chunk = Storage::disk($disk)->readStream($s3Path);
                if ($chunk === false) {
                    $file->update(['status' => FileStatus::Invalid->value]);

                    continue;
                }

                $firstBytes = '';
                $bytesRead = 0;
                $maxBytes = 512;

                while (! feof($chunk) && $bytesRead < $maxBytes) {
                    $data = fread($chunk, $maxBytes - $bytesRead);
                    if ($data === false) {
                        break;
                    }
                    $firstBytes .= $data;
                    $bytesRead += strlen($data);
                }
                fclose($chunk);

                // Validate file size matches (use loose comparison to handle type differences)
                if ($actualSize != $expectedSize) {
                    // Delete invalid file from S3
                    Storage::disk($disk)->delete($s3Path);
                    $file->update(['status' => FileStatus::Invalid->value]);

                    continue;
                }

                // Validate MIME type using finfo
                $finfo = finfo_open(FILEINFO_MIME_TYPE);
                $detectedMimeType = finfo_buffer($finfo, $firstBytes);
                finfo_close($finfo);

                $allowedMimeTypes = config('filesystems.allowed_mime_types', []);

                // Check if detected MIME type is in allowed list
                if (! in_array($detectedMimeType, $allowedMimeTypes, true)) {
                    // Delete invalid file from S3
                    Storage::disk($disk)->delete($s3Path);
                    $file->update(['status' => FileStatus::Invalid->value]);

                    continue;
                }

                // Mark as completed
                $file->update(['status' => FileStatus::Processing->value]);

                // Dispatch ProcessFileForVectorStore Job
                ProcessFileForVectorStore::dispatch($file->id);

                $validatedFiles[] = $file;
            } catch (\Exception $e) {
                // If validation fails, mark as invalid and delete from S3
                try {
                    Storage::disk($disk)->delete($s3Path);
                } catch (\Exception $deleteException) {
                    // Ignore delete errors
                }
                $file->update(['status' => FileStatus::Invalid->value]);
            }
        }

        return $validatedFiles;
    }
}
