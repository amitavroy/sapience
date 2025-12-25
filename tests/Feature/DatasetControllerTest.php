<?php

use App\Models\Dataset;
use App\Models\File;
use App\Models\Organisation;
use App\Models\User;
use Illuminate\Support\Facades\Storage;

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
    $response->assertInertia(
        fn ($page) => $page
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
    $response->assertInertia(
        fn ($page) => $page
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
    $response->assertInertia(
        fn ($page) => $page
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
    $response->assertInertia(
        fn ($page) => $page
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
    $response->assertInertia(
        fn ($page) => $page
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
    $response->assertInertia(
        fn ($page) => $page
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

test('admin can update dataset with instructions and output instructions', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
        'name' => 'Original Name',
    ]);

    $response = $this->actingAs($user)->put(
        route('organisations.datasets.update', [$organisation, $dataset]),
        [
            'name' => 'Updated Name',
            'instructions' => "Custom instruction 1\nCustom instruction 2",
            'output_instructions' => "Output instruction 1\nOutput instruction 2",
        ]
    );

    $response->assertRedirect();
    $response->assertSessionHas('success');

    $this->assertDatabaseHas('datasets', [
        'id' => $dataset->id,
        'name' => 'Updated Name',
        'instructions' => "Custom instruction 1\nCustom instruction 2",
        'output_instructions' => "Output instruction 1\nOutput instruction 2",
    ]);
});

test('admin can update dataset without instructions', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
        'name' => 'Original Name',
        'instructions' => 'Original Instructions',
        'output_instructions' => 'Original Output Instructions',
    ]);

    $response = $this->actingAs($user)->put(
        route('organisations.datasets.update', [$organisation, $dataset]),
        [
            'name' => 'Updated Name',
            'instructions' => null,
            'output_instructions' => null,
        ]
    );

    $response->assertRedirect();
    $response->assertSessionHas('success');

    $this->assertDatabaseHas('datasets', [
        'id' => $dataset->id,
        'name' => 'Updated Name',
        'instructions' => null,
        'output_instructions' => null,
    ]);
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
    $response->assertInertia(
        fn ($page) => $page
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
    $response->assertInertia(
        fn ($page) => $page
            ->has('datasets', 2)
            ->where('datasets.0.is_active', true)
            ->where('datasets.1.is_active', false)
    );
});

test('admin can delete a dataset', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $typesenseService = Mockery::mock(\App\Services\TypesenseService::class);
    $typesenseService->shouldReceive('deleteCollection')
        ->once()
        ->with($organisation->id, $dataset->id);

    $this->app->instance(\App\Services\TypesenseService::class, $typesenseService);

    $response = $this->actingAs($user)->delete(
        route('organisations.datasets.destroy', [$organisation, $dataset])
    );

    $response->assertRedirect();
    $response->assertSessionHas('success');

    $this->assertDatabaseMissing('datasets', [
        'id' => $dataset->id,
    ]);
});

test('non-admin cannot delete a dataset', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $response = $this->actingAs($user)->delete(
        route('organisations.datasets.destroy', [$organisation, $dataset])
    );

    $response->assertForbidden();

    $this->assertDatabaseHas('datasets', [
        'id' => $dataset->id,
    ]);
});

test('dataset deletion always deletes Typesense collection', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $typesenseService = Mockery::mock(\App\Services\TypesenseService::class);
    $typesenseService->shouldReceive('deleteCollection')
        ->once()
        ->with($organisation->id, $dataset->id);

    $this->app->instance(\App\Services\TypesenseService::class, $typesenseService);

    $this->actingAs($user)->delete(
        route('organisations.datasets.destroy', [$organisation, $dataset]),
        ['delete_files' => false, 'delete_conversations' => false]
    );

    $this->assertDatabaseMissing('datasets', [
        'id' => $dataset->id,
    ]);
});

test('dataset deletion with delete_files flag deletes exclusive files from S3', function () {
    Storage::fake('s3');
    Config::set('filesystems.uploads_disk', 's3');
    setUploadsDisk('s3');

    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $file = \App\Models\File::factory()->create(['user_id' => $user->id]);
    $dataset->files()->attach($file->id);

    $s3Path = "datasets/{$dataset->id}/files/{$file->filename}";
    Storage::disk('s3')->put($s3Path, 'test content');

    $typesenseService = Mockery::mock(\App\Services\TypesenseService::class);
    $typesenseService->shouldReceive('deleteCollection')
        ->once()
        ->with($organisation->id, $dataset->id);

    $this->app->instance(\App\Services\TypesenseService::class, $typesenseService);

    $this->actingAs($user)->delete(
        route('organisations.datasets.destroy', [$organisation, $dataset]),
        ['delete_files' => true, 'delete_conversations' => false]
    );

    $this->assertDatabaseMissing('datasets', [
        'id' => $dataset->id,
    ]);
    $this->assertDatabaseMissing('files', [
        'id' => $file->id,
    ]);
    Storage::disk('s3')->assertMissing($s3Path);
});

test('dataset deletion without delete_files flag does not delete files', function () {
    Storage::fake('s3');
    Config::set('filesystems.uploads_disk', 's3');
    setUploadsDisk('s3');

    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $file = \App\Models\File::factory()->create(['user_id' => $user->id]);
    $dataset->files()->attach($file->id);

    $s3Path = "datasets/{$dataset->id}/files/{$file->filename}";
    Storage::disk('s3')->put($s3Path, 'test content');

    $typesenseService = Mockery::mock(\App\Services\TypesenseService::class);
    $typesenseService->shouldReceive('deleteCollection')
        ->once()
        ->with($organisation->id, $dataset->id);

    $this->app->instance(\App\Services\TypesenseService::class, $typesenseService);

    $this->actingAs($user)->delete(
        route('organisations.datasets.destroy', [$organisation, $dataset]),
        ['delete_files' => false, 'delete_conversations' => false]
    );

    $this->assertDatabaseMissing('datasets', [
        'id' => $dataset->id,
    ]);
    // File should still exist
    $this->assertDatabaseHas('files', [
        'id' => $file->id,
    ]);
    // File should still be in S3
    Storage::disk('s3')->assertExists($s3Path);
});

test('dataset deletion with delete_files flag does not delete files belonging to other datasets', function () {
    Storage::fake('s3');
    Config::set('filesystems.uploads_disk', 's3');
    setUploadsDisk('s3');

    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $dataset1 = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $dataset2 = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $file = \App\Models\File::factory()->create(['user_id' => $user->id]);
    $dataset1->files()->attach($file->id);
    $dataset2->files()->attach($file->id);

    $s3Path = "datasets/{$dataset1->id}/files/{$file->filename}";
    Storage::disk('s3')->put($s3Path, 'test content');

    $typesenseService = Mockery::mock(\App\Services\TypesenseService::class);
    $typesenseService->shouldReceive('deleteCollection')
        ->once()
        ->with($organisation->id, $dataset1->id);

    $this->app->instance(\App\Services\TypesenseService::class, $typesenseService);

    $this->actingAs($user)->delete(
        route('organisations.datasets.destroy', [$organisation, $dataset1]),
        ['delete_files' => true, 'delete_conversations' => false]
    );

    $this->assertDatabaseMissing('datasets', [
        'id' => $dataset1->id,
    ]);
    // File should still exist because it belongs to dataset2
    $this->assertDatabaseHas('files', [
        'id' => $file->id,
    ]);
    // File should be detached from dataset1 but still attached to dataset2
    $this->assertDatabaseMissing('dataset_file', [
        'dataset_id' => $dataset1->id,
        'file_id' => $file->id,
    ]);
    $this->assertDatabaseHas('dataset_file', [
        'dataset_id' => $dataset2->id,
        'file_id' => $file->id,
    ]);
});

test('dataset deletion with delete_conversations flag deletes conversations', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $conversation = \App\Models\Conversation::factory()->create([
        'organisation_id' => $organisation->id,
        'dataset_id' => $dataset->id,
        'user_id' => $user->id,
    ]);

    $message = \App\Models\Message::create([
        'thread_id' => (string) $conversation->id,
        'role' => 'user',
        'content' => ['text' => 'Test message'],
    ]);

    $typesenseService = Mockery::mock(\App\Services\TypesenseService::class);
    $typesenseService->shouldReceive('deleteCollection')
        ->once()
        ->with($organisation->id, $dataset->id);

    $this->app->instance(\App\Services\TypesenseService::class, $typesenseService);

    $this->actingAs($user)->delete(
        route('organisations.datasets.destroy', [$organisation, $dataset]),
        ['delete_files' => false, 'delete_conversations' => true]
    );

    $this->assertDatabaseMissing('datasets', [
        'id' => $dataset->id,
    ]);
    $this->assertDatabaseMissing('conversations', [
        'id' => $conversation->id,
    ]);
    $this->assertDatabaseMissing('messages', [
        'id' => $message->id,
    ]);
});

test('dataset deletion without delete_conversations flag prevents deletion when conversations exist', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'admin']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $conversation = \App\Models\Conversation::factory()->create([
        'organisation_id' => $organisation->id,
        'dataset_id' => $dataset->id,
        'user_id' => $user->id,
    ]);

    $message = \App\Models\Message::create([
        'thread_id' => (string) $conversation->id,
        'role' => 'user',
        'content' => ['text' => 'Test message'],
    ]);

    $typesenseService = Mockery::mock(\App\Services\TypesenseService::class);
    // Typesense deletion should not be called if validation fails early
    $typesenseService->shouldNotReceive('deleteCollection');

    $this->app->instance(\App\Services\TypesenseService::class, $typesenseService);

    $response = $this->actingAs($user)->delete(
        route('organisations.datasets.destroy', [$organisation, $dataset]),
        ['delete_files' => false, 'delete_conversations' => false]
    );

    $response->assertStatus(500); // Server error due to exception

    // Dataset should still exist
    $this->assertDatabaseHas('datasets', [
        'id' => $dataset->id,
    ]);
    // Conversations should still exist
    $this->assertDatabaseHas('conversations', [
        'id' => $conversation->id,
    ]);
    $this->assertDatabaseHas('messages', [
        'id' => $message->id,
    ]);
});
