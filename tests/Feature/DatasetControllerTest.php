<?php

use App\Models\Dataset;
use App\Models\File;
use App\Models\Organisation;
use App\Models\User;
use Mockery;

test('user can view datasets index for their organisation', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $dataset1 = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);
    $dataset2 = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $response = $this->actingAs($user)->get(
        route('organisations.datasets.index', $organisation)
    );

    $response->assertSuccessful();
    $response->assertInertia(fn ($page) => $page
        ->component('organisations/datasets/index')
        ->has('datasets', 2)
        ->where('organisation.id', $organisation->id)
        ->where('isAdmin', false)
    );
});

test('admin can view datasets index and sees create button', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $response = $this->actingAs($user)->get(
        route('organisations.datasets.index', $organisation)
    );

    $response->assertSuccessful();
    $response->assertInertia(fn ($page) => $page
        ->component('organisations/datasets/index')
        ->where('isAdmin', true)
    );
});

test('user cannot view datasets for organisation they do not belong to', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $response = $this->actingAs($user)->get(
        route('organisations.datasets.index', $organisation)
    );

    $response->assertForbidden();
});

test('user can view a dataset they belong to', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $response = $this->actingAs($user)->get(
        route('organisations.datasets.show', [$organisation, $dataset])
    );

    $response->assertSuccessful();
    $response->assertInertia(fn ($page) => $page
        ->component('organisations/datasets/show')
        ->where('dataset.id', $dataset->id)
        ->where('dataset.name', $dataset->name)
        ->where('isAdmin', false)
    );
});

test('dataset show page displays file count', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $file1 = File::factory()->create(['user_id' => $user->id]);
    $file2 = File::factory()->create(['user_id' => $user->id]);
    $dataset->files()->attach([$file1->id, $file2->id]);

    $response = $this->actingAs($user)->get(
        route('organisations.datasets.show', [$organisation, $dataset])
    );

    $response->assertSuccessful();
    $response->assertInertia(fn ($page) => $page
        ->where('dataset.files_count', 2)
    );
});

test('user cannot view dataset from different organisation', function () {
    $user = User::factory()->create();
    $organisation1 = Organisation::factory()->create();
    $organisation2 = Organisation::factory()->create();
    $user->organisations()->attach($organisation1->id, ['role' => 'member']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation2->id,
        'owner_id' => $user->id,
    ]);

    $response = $this->actingAs($user)->get(
        route('organisations.datasets.show', [$organisation1, $dataset])
    );

    $response->assertNotFound();
});

test('admin can access create dataset page', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $response = $this->actingAs($user)->get(
        route('organisations.datasets.create', $organisation)
    );

    $response->assertSuccessful();
    $response->assertInertia(fn ($page) => $page
        ->component('organisations/datasets/create')
        ->where('organisation.id', $organisation->id)
    );
});

test('non-admin cannot access create dataset page', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $response = $this->actingAs($user)->get(
        route('organisations.datasets.create', $organisation)
    );

    $response->assertForbidden();
});

test('admin can create a dataset', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $typesenseService = Mockery::mock(\App\Services\TypesenseService::class);
    $typesenseService->shouldReceive('createCollection')
        ->once()
        ->with($organisation->id, Mockery::type('int'));

    $this->app->instance(\App\Services\TypesenseService::class, $typesenseService);

    $response = $this->actingAs($user)->post(
        route('organisations.datasets.store', $organisation),
        [
            'name' => 'Test Dataset',
            'description' => 'Test Description',
        ]
    );

    $response->assertRedirect();
    $response->assertSessionHas('success');

    $this->assertDatabaseHas('datasets', [
        'name' => 'Test Dataset',
        'description' => 'Test Description',
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
        'is_active' => true,
    ]);
});

test('non-admin cannot create a dataset', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $response = $this->actingAs($user)->post(
        route('organisations.datasets.store', $organisation),
        [
            'name' => 'Test Dataset',
            'description' => 'Test Description',
        ]
    );

    $response->assertForbidden();
    $this->assertDatabaseMissing('datasets', [
        'name' => 'Test Dataset',
    ]);
});

test('dataset creation requires name', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $response = $this->actingAs($user)->post(
        route('organisations.datasets.store', $organisation),
        [
            'description' => 'Test Description',
        ]
    );

    $response->assertSessionHasErrors('name');
});

test('admin can access edit dataset page', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $response = $this->actingAs($user)->get(
        route('organisations.datasets.edit', [$organisation, $dataset])
    );

    $response->assertSuccessful();
    $response->assertInertia(fn ($page) => $page
        ->component('organisations/datasets/edit')
        ->where('dataset.id', $dataset->id)
    );
});

test('non-admin cannot access edit dataset page', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $response = $this->actingAs($user)->get(
        route('organisations.datasets.edit', [$organisation, $dataset])
    );

    $response->assertForbidden();
});

test('admin can update a dataset', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
        'name' => 'Original Name',
        'description' => 'Original Description',
    ]);

    $response = $this->actingAs($user)->put(
        route('organisations.datasets.update', [$organisation, $dataset]),
        [
            'name' => 'Updated Name',
            'description' => 'Updated Description',
        ]
    );

    $response->assertRedirect();
    $response->assertSessionHas('success');

    $this->assertDatabaseHas('datasets', [
        'id' => $dataset->id,
        'name' => 'Updated Name',
        'description' => 'Updated Description',
    ]);
});

test('non-admin cannot update a dataset', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
        'name' => 'Original Name',
    ]);

    $response = $this->actingAs($user)->put(
        route('organisations.datasets.update', [$organisation, $dataset]),
        [
            'name' => 'Updated Name',
        ]
    );

    $response->assertForbidden();

    $this->assertDatabaseHas('datasets', [
        'id' => $dataset->id,
        'name' => 'Original Name',
    ]);
});

test('dataset update requires name', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $response = $this->actingAs($user)->put(
        route('organisations.datasets.update', [$organisation, $dataset]),
        [
            'description' => 'Updated Description',
        ]
    );

    $response->assertSessionHasErrors('name');
});

test('datasets index shows file count', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $file1 = File::factory()->create(['user_id' => $user->id]);
    $file2 = File::factory()->create(['user_id' => $user->id]);
    $dataset->files()->attach([$file1->id, $file2->id]);

    $response = $this->actingAs($user)->get(
        route('organisations.datasets.index', $organisation)
    );

    $response->assertSuccessful();
    $response->assertInertia(fn ($page) => $page
        ->has('datasets', 1)
        ->where('datasets.0.files_count', 2)
    );
});

test('datasets index shows status correctly', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $activeDataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
        'is_active' => true,
    ]);

    $inactiveDataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
        'is_active' => false,
    ]);

    $response = $this->actingAs($user)->get(
        route('organisations.datasets.index', $organisation)
    );

    $response->assertSuccessful();
    $response->assertInertia(fn ($page) => $page
        ->has('datasets', 2)
        ->where('datasets.0.is_active', true)
        ->where('datasets.1.is_active', false)
    );
});
