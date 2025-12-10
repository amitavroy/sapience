<?php

namespace App\Actions;

use App\Enums\FileStatus;
use App\Models\Dataset;
use App\Models\File;
use App\Models\User;
use App\Services\SignedUrlService;
use Illuminate\Support\Arr;
use Illuminate\Support\Facades\DB;
use Illuminate\Support\Str;

class RequestFileUploadAction
{
    /**
     * Request file upload URLs for multiple files.
     *
     * @param  array<int, array{original_filename: string, file_size: int, mime_type: string}>  $files
     * @return array<int, array{file_id: int, upload_url: string, headers: array<string, string>}>
     */
    public function __construct(
        private readonly SignedUrlService $signedUrlService
    ) {}

    public function execute(array $files, Dataset $dataset, User $user): array
    {
        $results = [];

        foreach ($files as $fileData) {
            $originalFilename = Arr::get($fileData, 'original_filename');
            $fileSize = Arr::get($fileData, 'file_size');
            $mimeType = Arr::get($fileData, 'mime_type');

            // Generate unique filename
            $extension = pathinfo($originalFilename, PATHINFO_EXTENSION);
            $filename = Str::uuid()->toString().($extension ? '.'.$extension : '');

            // Create file record with pending status and associate with dataset in a transaction
            $file = DB::transaction(function () use ($originalFilename, $filename, $fileSize, $mimeType, $user, $dataset) {
                // Create file record with pending status
                $file = File::create([
                    'original_filename' => $originalFilename,
                    'filename' => $filename,
                    'file_size' => $fileSize,
                    'mime_type' => $mimeType,
                    'status' => FileStatus::Pending->value,
                    'user_id' => $user->id,
                ]);

                // Associate file with dataset
                $dataset->files()->attach($file->id);

                return $file;
            });

            // Generate storage path
            $storagePath = "datasets/{$dataset->id}/files/{$filename}";

            // Generate temporary upload URL (expires in 1 hour)
            ['url' => $uploadUrl, 'headers' => $headers] = $this->signedUrlService->generateSignedUploadUrl(
                $storagePath,
                now()->addHour()
            );

            $results[] = [
                'file_id' => $file->id,
                'upload_url' => $uploadUrl,
                'headers' => $headers,
            ];
        }

        return $results;
    }
}
