<?php

use App\Actions\CreateDatasetAction;
use App\Models\Dataset;
use App\Models\Organisation;
use App\Models\User;
use App\Services\TypesenseService;
use Illuminate\Foundation\Testing\RefreshDatabase;
use Tests\TestCase;

uses(TestCase::class, RefreshDatabase::class);

test('creates a dataset with correct attributes', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $capturedDatasetId = null;
    $typesenseService = Mockery::mock(TypesenseService::class);
    $typesenseService->shouldReceive('createCollection')
        ->once()
        ->with($organisation->id, Mockery::on(function ($datasetId) use (&$capturedDatasetId) {
            $capturedDatasetId = $datasetId;

            return is_int($datasetId) && $datasetId > 0;
        }));

    $action = new CreateDatasetAction($typesenseService);

    $validated = [
        'name' => 'Test Dataset',
        'description' => 'Test Description',
    ];

    $dataset = $action->execute($validated, $organisation, $user);

    expect($dataset)->toBeInstanceOf(Dataset::class);
    expect($dataset->name)->toBe('Test Dataset');
    expect($dataset->description)->toBe('Test Description');
    expect($dataset->organisation_id)->toBe($organisation->id);
    expect($dataset->owner_id)->toBe($user->id);
    expect($dataset->is_active)->toBeTrue();
    expect($dataset->exists)->toBeTrue();
    expect($capturedDatasetId)->toBe($dataset->id);
});

test('creates a dataset with only name when description is missing', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $capturedDatasetId = null;
    $typesenseService = Mockery::mock(TypesenseService::class);
    $typesenseService->shouldReceive('createCollection')
        ->once()
        ->with($organisation->id, Mockery::on(function ($datasetId) use (&$capturedDatasetId) {
            $capturedDatasetId = $datasetId;

            return is_int($datasetId) && $datasetId > 0;
        }));

    $action = new CreateDatasetAction($typesenseService);

    $validated = [
        'name' => 'Test Dataset',
    ];

    $dataset = $action->execute($validated, $organisation, $user);

    expect($dataset)->toBeInstanceOf(Dataset::class);
    expect($dataset->name)->toBe('Test Dataset');
    expect($dataset->description)->toBeNull();
    expect($dataset->organisation_id)->toBe($organisation->id);
    expect($dataset->owner_id)->toBe($user->id);
    expect($dataset->is_active)->toBeTrue();
    expect($capturedDatasetId)->toBe($dataset->id);
});

test('calls typesense service with correct organisation and dataset ids', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $capturedDatasetId = null;
    $typesenseService = Mockery::mock(TypesenseService::class);
    $typesenseService->shouldReceive('createCollection')
        ->once()
        ->with($organisation->id, Mockery::on(function ($datasetId) use (&$capturedDatasetId) {
            $capturedDatasetId = $datasetId;

            return is_int($datasetId) && $datasetId > 0;
        }));

    $action = new CreateDatasetAction($typesenseService);

    $validated = [
        'name' => 'Test Dataset',
        'description' => 'Test Description',
    ];

    $dataset = $action->execute($validated, $organisation, $user);

    // Verify the dataset was created and the IDs match
    expect($dataset->organisation_id)->toBe($organisation->id);
    expect($dataset->owner_id)->toBe($user->id);
    expect($capturedDatasetId)->toBe($dataset->id);
});
