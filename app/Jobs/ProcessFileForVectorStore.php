<?php

namespace App\Jobs;

use App\Enums\FileStatus;
use App\Models\File;
use App\Neuron\SapienceBot;
use App\Services\UtilService;
use Illuminate\Contracts\Queue\ShouldQueue;
use Illuminate\Foundation\Queue\Queueable;
use Illuminate\Support\Benchmark;
use Illuminate\Support\Facades\Log;
use Illuminate\Support\Facades\Storage;
use NeuronAI\RAG\DataLoader\FileDataLoader;

class ProcessFileForVectorStore implements ShouldQueue
{
    use Queueable;

    /**
     * Create a new job instance.
     */
    public function __construct(
        public int $fileId
    ) {
        //
    }

    /**
     * Execute the job.
     */
    public function handle(): void
    {
        try {
            // Get the file again from the database
            $file = File::with(['datasets.organisation'])->findOrFail($this->fileId);

            // Get the dataset from the file's relation (get first dataset)
            $dataset = $file->datasets->first();

            if (! $dataset) {
                Log::warning('File has no associated dataset', [
                    'file_id' => $file->id,
                    'file_uuid' => $file->uuid,
                ]);

                $file->update(['status' => FileStatus::Failed->value]);

                return;
            }

            // Get the organisation from the dataset's relation
            $organisation = $dataset->organisation;

            if (! $organisation) {
                Log::warning('Dataset has no associated organisation', [
                    'file_id' => $file->id,
                    'file_uuid' => $file->uuid,
                    'dataset_id' => $dataset->id,
                    'dataset_uuid' => $dataset->uuid,
                ]);

                $file->update(['status' => FileStatus::Failed->value]);

                return;
            }

            // Log them here
            Log::info('Processing file for vector store', [
                'file' => [
                    'id' => $file->id,
                    'uuid' => $file->uuid,
                    'original_filename' => $file->original_filename,
                    'filename' => $file->filename,
                    'status' => $file->status->value,
                ],
                'dataset' => [
                    'id' => $dataset->id,
                    'uuid' => $dataset->uuid,
                    'name' => $dataset->name,
                ],
                'organisation' => [
                    'id' => $organisation->id,
                    'uuid' => $organisation->uuid,
                    'name' => $organisation->name,
                ],
            ]);

            // get the file from S3
            $s3Path = UtilService::getFileS3Path($dataset, $file);

            if (! Storage::disk('s3')->exists($s3Path)) {
                Log::error('File not found in S3', [
                    'file_id' => $file->id,
                    'file_uuid' => $file->uuid,
                    's3_path' => $s3Path,
                ]);

                $file->update(['status' => FileStatus::Failed->value]);

                return;
            }

            $fileContent = Storage::disk('s3')->get($s3Path);

            // save the S3 file into storage/temp folder as a temporary file
            $tempPath = storage_path('app/temp/'.$file->filename);
            $tempDir = dirname($tempPath);

            // Ensure temp directory exists
            if (! is_dir($tempDir)) {
                mkdir($tempDir, 0755, true);
            }

            // Save file content to temporary file
            file_put_contents($tempPath, $fileContent);

            try {
                // Measure time taken to add documents to vector store
                [, $duration] = Benchmark::value(function () use ($tempPath) {
                    SapienceBot::make()->addDocuments(
                        documents: FileDataLoader::for($tempPath)->getDocuments()
                    );
                });

                Log::info('File added to vector store', [
                    'file_id' => $file->id,
                    'file_name' => $file->filename,
                    'duration_ms' => round($duration, 2),
                ]);

                $file->update(['status' => FileStatus::Completed->value]);
            } catch (\Throwable $e) {
                Log::error('Failed to add file to vector store', [
                    'file_id' => $file->id,
                    'file_uuid' => $file->uuid,
                    'file_name' => $file->filename,
                    'error' => $e->getMessage(),
                    'trace' => $e->getTraceAsString(),
                ]);

                $file->update(['status' => FileStatus::Failed->value]);

                throw $e;
            } finally {
                // Clean up temporary file
                if (file_exists($tempPath)) {
                    unlink($tempPath);
                    Log::info('Temporary file deleted', [
                        'file_path' => $tempPath,
                    ]);
                }
            }
        } catch (\Throwable $e) {
            // Catch any other exceptions (e.g., file not found, database errors)
            $file = File::find($this->fileId);

            if ($file) {
                Log::error('ProcessFileForVectorStore job failed', [
                    'file_id' => $this->fileId,
                    'file_uuid' => $file->uuid ?? null,
                    'error' => $e->getMessage(),
                    'trace' => $e->getTraceAsString(),
                ]);

                $file->update(['status' => FileStatus::Failed->value]);
            }

            throw $e;
        }
    }
}
