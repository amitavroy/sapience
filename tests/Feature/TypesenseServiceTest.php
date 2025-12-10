<?php

use App\Services\TypesenseService;
use Illuminate\Support\Facades\Config;
use Typesense\Client;
use Typesense\Collection;
use Typesense\Collections;
use Typesense\Exceptions\ObjectNotFound;
use Typesense\Exceptions\TypesenseClientError;

beforeEach(function () {
    Config::set('services.typesense', [
        'host' => 'localhost',
        'port' => '8108',
        'protocol' => 'http',
        'api_key' => 'test-key',
    ]);
});

test('getCollectionName returns correct format', function () {
    $service = new TypesenseService;
    $collectionName = $service->getCollectionName(1, 2);

    expect($collectionName)->toBe('sapience_org_1_dataset_2');
});

test('collectionExists returns true when collection exists', function () {
    $collectionName = 'sapience_org_1_dataset_2';
    $collectionMock = Mockery::mock(Collection::class);
    $collectionsMock = Mockery::mock(Collections::class);
    $clientMock = Mockery::mock(Client::class);

    $collectionMock->shouldReceive('retrieve')
        ->once()
        ->andReturn(['name' => $collectionName]);

    $collectionsMock->shouldReceive('offsetGet')
        ->with($collectionName)
        ->andReturn($collectionMock);

    $clientMock->collections = $collectionsMock;

    $service = new TypesenseService;
    $reflection = new ReflectionClass($service);
    $property = $reflection->getProperty('client');
    $property->setAccessible(true);
    $property->setValue($service, $clientMock);

    expect($service->collectionExists($collectionName))->toBeTrue();
});

test('collectionExists returns false when collection does not exist', function () {
    $collectionName = 'sapience_org_1_dataset_2';
    $collectionMock = Mockery::mock(Collection::class);
    $collectionsMock = Mockery::mock(Collections::class);
    $clientMock = Mockery::mock(Client::class);

    $error = new ObjectNotFound('Not found');
    $collectionMock->shouldReceive('retrieve')
        ->once()
        ->andThrow($error);

    $collectionsMock->shouldReceive('offsetGet')
        ->with($collectionName)
        ->andReturn($collectionMock);

    $clientMock->collections = $collectionsMock;

    $service = new TypesenseService;
    $reflection = new ReflectionClass($service);
    $property = $reflection->getProperty('client');
    $property->setAccessible(true);
    $property->setValue($service, $clientMock);

    expect($service->collectionExists($collectionName))->toBeFalse();
});

test('collectionExists throws exception for non-404 errors', function () {
    $collectionName = 'sapience_org_1_dataset_2';
    $collectionMock = Mockery::mock(Collection::class);
    $collectionsMock = Mockery::mock(Collections::class);
    $clientMock = Mockery::mock(Client::class);

    $error = new TypesenseClientError('Server error', 500);
    $collectionMock->shouldReceive('retrieve')
        ->once()
        ->andThrow($error);

    $collectionsMock->shouldReceive('offsetGet')
        ->with($collectionName)
        ->andReturn($collectionMock);

    $clientMock->collections = $collectionsMock;

    $service = new TypesenseService;
    $reflection = new ReflectionClass($service);
    $property = $reflection->getProperty('client');
    $property->setAccessible(true);
    $property->setValue($service, $clientMock);

    expect(fn () => $service->collectionExists($collectionName))
        ->toThrow(TypesenseClientError::class);
});

test('createCollection throws exception when collection already exists', function () {
    $organisationId = 1;
    $datasetId = 2;
    $collectionName = 'sapience_org_1_dataset_2';

    $collectionMock = Mockery::mock(Collection::class);
    $collectionsMock = Mockery::mock(Collections::class);
    $clientMock = Mockery::mock(Client::class);

    $collectionMock->shouldReceive('retrieve')
        ->once()
        ->andReturn(['name' => $collectionName]);

    $collectionsMock->shouldReceive('offsetGet')
        ->with($collectionName)
        ->andReturn($collectionMock);

    $clientMock->collections = $collectionsMock;

    $service = new TypesenseService;
    $reflection = new ReflectionClass($service);
    $property = $reflection->getProperty('client');
    $property->setAccessible(true);
    $property->setValue($service, $clientMock);

    expect(fn () => $service->createCollection($organisationId, $datasetId))
        ->toThrow(\RuntimeException::class, "Collection '{$collectionName}' already exists.");
});

test('createCollection successfully creates collection', function () {
    $organisationId = 1;
    $datasetId = 2;
    $collectionName = 'sapience_org_1_dataset_2';

    $collectionMock = Mockery::mock(Collection::class);
    $collectionsMock = Mockery::mock(Collections::class);
    $clientMock = Mockery::mock(Client::class);

    $error = new ObjectNotFound('Not found');
    $collectionMock->shouldReceive('retrieve')
        ->once()
        ->andThrow($error);

    $collectionsMock->shouldReceive('offsetGet')
        ->with($collectionName)
        ->andReturn($collectionMock);

    $collectionsMock->shouldReceive('create')
        ->once()
        ->with(Mockery::on(function ($schema) use ($collectionName) {
            return $schema['name'] === $collectionName
                && count($schema['fields']) === 8
                && $schema['enable_nested_fields'] === true;
        }))
        ->andReturn(['name' => $collectionName]);

    $clientMock->collections = $collectionsMock;

    $service = new TypesenseService;
    $reflection = new ReflectionClass($service);
    $property = $reflection->getProperty('client');
    $property->setAccessible(true);
    $property->setValue($service, $clientMock);

    $service->createCollection($organisationId, $datasetId);

    expect(true)->toBeTrue();
});

test('createCollection throws exception when Typesense client error occurs', function () {
    $organisationId = 1;
    $datasetId = 2;
    $collectionName = 'sapience_org_1_dataset_2';

    $collectionMock = Mockery::mock(Collection::class);
    $collectionsMock = Mockery::mock(Collections::class);
    $clientMock = Mockery::mock(Client::class);

    $error = new ObjectNotFound('Not found');
    $collectionMock->shouldReceive('retrieve')
        ->once()
        ->andThrow($error);

    $collectionsMock->shouldReceive('offsetGet')
        ->with($collectionName)
        ->andReturn($collectionMock);

    $createError = new TypesenseClientError('Invalid schema');
    $collectionsMock->shouldReceive('create')
        ->once()
        ->andThrow($createError);

    $clientMock->collections = $collectionsMock;

    $service = new TypesenseService;
    $reflection = new ReflectionClass($service);
    $property = $reflection->getProperty('client');
    $property->setAccessible(true);
    $property->setValue($service, $clientMock);

    expect(fn () => $service->createCollection($organisationId, $datasetId))
        ->toThrow(\RuntimeException::class, "Failed to create Typesense collection '{$collectionName}': Invalid schema");
});
