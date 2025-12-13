<?php

namespace App\Services;

use Typesense\Client;
use Typesense\Exceptions\ObjectNotFound;
use Typesense\Exceptions\TypesenseClientError;

class TypesenseService
{
    private Client $client;

    public function __construct()
    {
        $this->client = new Client([
            'nodes' => [
                [
                    'host' => config('services.typesense.host'),
                    'port' => config('services.typesense.port'),
                    'protocol' => config('services.typesense.protocol'),
                ],
            ],
            'api_key' => config('services.typesense.api_key'),
            'connection_timeout_seconds' => 2,
        ]);
    }

    public function getClient(): Client
    {
        return $this->client;
    }

    /**
     * Get the collection name for a given organisation and dataset.
     */
    public function getCollectionName(int $organisationId, int $datasetId): string
    {
        return "sapience_org_{$organisationId}_dataset_{$datasetId}";
    }

    /**
     * Get the embedding dimension based on the configured model.
     */
    public static function getEmbeddingDimension(): int
    {
        $model = config('services.openai.embeddings_model');

        return match ($model) {
            'text-embedding-3-large' => 1024, // Can be 1024, 256, or 3072 depending on dimensions parameter
            'text-embedding-3-small' => 1536,
            'text-embedding-ada-002' => 1536,
            default => 1024,
        };
    }

    /**
     * Check if a collection exists.
     */
    public function collectionExists(string $collectionName): bool
    {
        try {
            $this->client->collections[$collectionName]->retrieve();

            return true;
        } catch (ObjectNotFound $e) {
            return false;
        } catch (TypesenseClientError $e) {
            throw $e;
        }
    }

    /**
     * Create a Typesense collection for the given organisation and dataset.
     *
     * @throws \RuntimeException if collection already exists or creation fails
     */
    public function createCollection(int $organisationId, int $datasetId, ?int $vectorDimension = null): void
    {
        $vectorDimension = $vectorDimension ?? self::getEmbeddingDimension();
        $collectionName = $this->getCollectionName($organisationId, $datasetId);

        if ($this->collectionExists($collectionName)) {
            throw new \RuntimeException("Collection '{$collectionName}' already exists.");
        }

        $schema = [
            'name' => $collectionName,
            'fields' => [
                [
                    'name' => 'content',
                    'type' => 'string',
                    'store' => true,
                ],
                [
                    'name' => 'embedding',
                    'type' => 'float[]',
                    'num_dim' => $vectorDimension,
                ],
                [
                    'name' => 'sourceType',
                    'type' => 'string',
                    'facet' => true,
                    'optional' => false,
                ],
                [
                    'name' => 'sourceName',
                    'type' => 'string',
                    'facet' => true,
                    'optional' => false,
                ],
                [
                    'name' => 'file_id',
                    'type' => 'string',
                    'facet' => true,
                    'optional' => true,
                ],
                [
                    'name' => 'file_uuid',
                    'type' => 'string',
                    'facet' => true,
                    'optional' => true,
                ],
                [
                    'name' => 'chunk_index',
                    'type' => 'int32',
                    'optional' => true,
                ],
                [
                    'name' => 'original_filename',
                    'type' => 'string',
                    'facet' => true,
                    'optional' => true,
                ],
                [
                    'name' => 'filename',
                    'type' => 'string',
                    'facet' => true,
                    'optional' => true,
                ],
                [
                    'name' => 'mime_type',
                    'type' => 'string',
                    'facet' => true,
                    'optional' => true,
                ],
                [
                    'name' => 'created_at',
                    'type' => 'int64',
                    'optional' => true,
                ],
            ],
            'enable_nested_fields' => true,
        ];

        try {
            $this->client->collections->create($schema);
        } catch (TypesenseClientError $e) {
            throw new \RuntimeException(
                "Failed to create Typesense collection '{$collectionName}': {$e->getMessage()}",
                0,
                $e
            );
        }
    }
}
