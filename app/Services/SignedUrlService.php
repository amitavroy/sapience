<?php

namespace App\Services;

use DateTimeInterface;
use Illuminate\Support\Facades\Storage;

class SignedUrlService
{
    /**
     * Get the storage disk name to use.
     * Uses the 'minio' disk by default, which can be configured for either MinIO or AWS S3.
     */
    private function getDiskName(): string
    {
        return env('FILESYSTEM_UPLOADS_DISK', 'minio');
    }

    /**
     * Generate a signed upload URL for a file path.
     *
     * @return array{url: string, headers: array<string, array<string>>}
     */
    public function generateSignedUploadUrl(string $path, DateTimeInterface $expiresAt): array
    {
        $diskName = $this->getDiskName();
        $disk = Storage::disk($diskName);

        // Only override endpoint for MinIO (local development)
        // For AWS S3, use the endpoint as-is since it's already publicly accessible
        if ($this->isMinIO()) {
            return $this->generateMinIOSignedUrl($disk, $path, $expiresAt);
        }

        // For AWS S3, generate URL normally
        return $disk->temporaryUploadUrl($path, $expiresAt);
    }

    /**
     * Get a public URL for a file path.
     */
    public function getPublicUrl(string $path): ?string
    {
        $diskName = $this->getDiskName();
        $disk = Storage::disk($diskName);

        if ($this->isMinIO()) {
            $externalUrl = config("filesystems.disks.{$diskName}.url");
            $bucket = config("filesystems.disks.{$diskName}.bucket");

            if ($externalUrl && $bucket) {
                return rtrim($externalUrl, '/') . '/' . $bucket . '/' . ltrim($path, '/');
            }
        }

        return $disk->url($path);
    }

    /**
     * Check if the configured storage is MinIO.
     */
    public function isMinIO(): bool
    {
        $diskName = $this->getDiskName();
        $endpoint = config("filesystems.disks.{$diskName}.endpoint");

        if (! $endpoint) {
            return false;
        }

        return str_contains($endpoint, 'minio') ||
            str_contains($endpoint, 'host.docker.internal') ||
            str_contains($endpoint, 'localhost');
    }

    /**
     * Generate a signed URL for MinIO with endpoint override.
     *
     * @param  \Illuminate\Contracts\Filesystem\Filesystem  $disk
     * @return array{url: string, headers: array<string, array<string>>}
     */
    private function generateMinIOSignedUrl($disk, string $path, DateTimeInterface $expiresAt): array
    {
        // Temporarily override endpoint to use external URL (localhost) for browser-accessible signed URLs
        $diskName = $this->getDiskName();
        $originalEndpoint = config("filesystems.disks.{$diskName}.endpoint");
        $externalEndpoint = config("filesystems.disks.{$diskName}.url") ?: 'http://localhost:9000';

        // Set the new endpoint in config
        config(["filesystems.disks.{$diskName}.endpoint" => $externalEndpoint]);

        // Clear the Storage cache to force a new client instance
        Storage::forgetDisk($diskName);

        // Recreate the disk with the new endpoint configuration
        $disk = Storage::disk($diskName);

        // Generate temporary upload URL
        $result = $disk->temporaryUploadUrl($path, $expiresAt);

        // Replace internal hostname with external URL in case the client was already instantiated
        if ($originalEndpoint && $externalEndpoint) {
            $result['url'] = str_replace($originalEndpoint, $externalEndpoint, $result['url']);

            // Update Host header to match the external URL
            if (isset($result['headers']['Host'])) {
                $externalHost = parse_url($externalEndpoint, PHP_URL_HOST);
                $externalPort = parse_url($externalEndpoint, PHP_URL_PORT);
                $result['headers']['Host'] = $externalPort
                    ? ["{$externalHost}:{$externalPort}"]
                    : [$externalHost];
            }
        }

        // Restore original endpoint and clear cache again
        config(["filesystems.disks.{$diskName}.endpoint" => $originalEndpoint]);
        Storage::forgetDisk($diskName);

        return $result;
    }
}
