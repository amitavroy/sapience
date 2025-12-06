<?php

use App\Models\Dataset;
use App\Models\File;
use App\Models\Organisation;
use App\Models\User;
use App\Queries\GetOrganisationDatasetsQuery;

test('query returns datasets for organisation', function () {
    $organisation = Organisation::factory()->create();
    $user = User::factory()->create();

    $dataset1 = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);
    $dataset2 = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $query = new GetOrganisationDatasetsQuery;
    $datasets = $query->execute($organisation)->get();

    expect($datasets)->toHaveCount(2);
    expect($datasets->pluck('id')->toArray())->toContain($dataset1->id, $dataset2->id);
});

test('query includes files count', function () {
    $organisation = Organisation::factory()->create();
    $user = User::factory()->create();
    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $file1 = File::factory()->create(['user_id' => $user->id]);
    $file2 = File::factory()->create(['user_id' => $user->id]);
    $dataset->files()->attach([$file1->id, $file2->id]);

    $query = new GetOrganisationDatasetsQuery;
    $datasets = $query->execute($organisation)->get();

    expect($datasets->first()->files_count)->toBe(2);
});

test('query includes owner relationship', function () {
    $organisation = Organisation::factory()->create();
    $user = User::factory()->create();
    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $query = new GetOrganisationDatasetsQuery;
    $datasets = $query->execute($organisation)->get();

    $resultDataset = $datasets->first();
    expect($resultDataset->relationLoaded('owner'))->toBeTrue();
    expect($resultDataset->owner)->toBeInstanceOf(User::class);
    expect($resultDataset->owner->id)->toBe($user->id);
});

test('query orders datasets by latest', function () {
    $organisation = Organisation::factory()->create();
    $user = User::factory()->create();

    $oldDataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
        'created_at' => now()->subDay(),
    ]);

    $newDataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
        'created_at' => now(),
    ]);

    $query = new GetOrganisationDatasetsQuery;
    $datasets = $query->execute($organisation)->get();

    expect($datasets->first()->id)->toBe($newDataset->id);
    expect($datasets->last()->id)->toBe($oldDataset->id);
});

test('query only returns datasets for specified organisation', function () {
    $organisation1 = Organisation::factory()->create();
    $organisation2 = Organisation::factory()->create();
    $user = User::factory()->create();

    $dataset1 = Dataset::factory()->create([
        'organisation_id' => $organisation1->id,
        'owner_id' => $user->id,
    ]);

    $dataset2 = Dataset::factory()->create([
        'organisation_id' => $organisation2->id,
        'owner_id' => $user->id,
    ]);

    $query = new GetOrganisationDatasetsQuery;
    $datasets = $query->execute($organisation1)->get();

    expect($datasets)->toHaveCount(1);
    expect($datasets->first()->id)->toBe($dataset1->id);
    expect($datasets->pluck('id'))->not->toContain($dataset2->id);
});

test('query returns empty collection when organisation has no datasets', function () {
    $organisation = Organisation::factory()->create();

    $query = new GetOrganisationDatasetsQuery;
    $datasets = $query->execute($organisation)->get();

    expect($datasets)->toBeEmpty();
});
