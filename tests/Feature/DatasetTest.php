<?php

use App\Models\Dataset;
use App\Models\File;
use App\Models\Organisation;
use App\Models\User;
use Illuminate\Support\Str;

test('dataset can be created with uuid and required fields', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $dataset = Dataset::factory()->create([
        'name' => 'Test Dataset',
        'description' => 'Test Description',
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    expect($dataset->name)->toBe('Test Dataset');
    expect($dataset->description)->toBe('Test Description');
    expect($dataset->uuid)->not->toBeNull();
    expect($dataset->uuid)->toBeString();
    expect($dataset->is_active)->toBeTrue();
});

test('dataset uuid is unique', function () {
    $uuid = (string) Str::uuid();

    Dataset::factory()->create(['uuid' => $uuid]);

    expect(fn() => Dataset::factory()->create(['uuid' => $uuid]))
        ->toThrow(\Illuminate\Database\QueryException::class);
});

test('dataset belongs to organisation', function () {
    $organisation = Organisation::factory()->create();
    $user = User::factory()->create();

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    expect($dataset->organisation)->toBeInstanceOf(Organisation::class);
    expect($dataset->organisation->id)->toBe($organisation->id);
    expect($dataset->organisation_id)->toBe($organisation->id);
});

test('dataset belongs to user as owner', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    expect($dataset->owner)->toBeInstanceOf(User::class);
    expect($dataset->owner->id)->toBe($user->id);
    expect($dataset->owner_id)->toBe($user->id);
});

test('user as owner has many datasets', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $dataset1 = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);
    $dataset2 = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    expect($user->datasets)->toHaveCount(2);
    expect($user->datasets->pluck('id')->toArray())->toContain($dataset1->id, $dataset2->id);
});

test('organisation has many datasets', function () {
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

    expect($organisation->datasets)->toHaveCount(2);
    expect($organisation->datasets->pluck('id')->toArray())->toContain($dataset1->id, $dataset2->id);
});

test('dataset can have multiple files', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    $file1 = File::factory()->create(['user_id' => $user->id]);
    $file2 = File::factory()->create(['user_id' => $user->id]);

    $dataset->files()->attach($file1->id);
    $dataset->files()->attach($file2->id);

    expect($dataset->files)->toHaveCount(2);
    expect($dataset->files->pluck('id')->toArray())->toContain($file1->id, $file2->id);
});

test('file can belong to multiple datasets', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $file = File::factory()->create(['user_id' => $user->id]);

    $dataset1 = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);
    $dataset2 = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    $file->datasets()->attach($dataset1->id);
    $file->datasets()->attach($dataset2->id);

    expect($file->datasets)->toHaveCount(2);
    expect($file->datasets->pluck('id')->toArray())->toContain($dataset1->id, $dataset2->id);
});

test('file count works correctly', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    expect($dataset->files()->count())->toBe(0);

    $file1 = File::factory()->create(['user_id' => $user->id]);
    $file2 = File::factory()->create(['user_id' => $user->id]);

    $dataset->files()->attach($file1->id);
    $dataset->files()->attach($file2->id);

    $dataset->refresh();

    expect($dataset->files()->count())->toBe(2);
});

test('dataset uses uuid for route model binding', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);

    expect($dataset->getRouteKeyName())->toBe('uuid');
    expect(Dataset::where('uuid', $dataset->uuid)->first()->id)->toBe($dataset->id);
});

test('dataset uuid is auto-generated on create', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $dataset = new Dataset([
        'name' => 'Test Dataset',
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);
    $dataset->save();

    expect($dataset->uuid)->not->toBeNull();
    expect($dataset->uuid)->toBeString();
    expect($dataset->uuid)->toMatch('/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i');
});

test('dataset uuid is not overwritten if already set', function () {
    $customUuid = (string) Str::uuid();
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $dataset = new Dataset([
        'name' => 'Test Dataset',
        'uuid' => $customUuid,
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);
    $dataset->save();

    expect($dataset->uuid)->toBe($customUuid);
});

test('file belongs to user who uploaded it', function () {
    $user = User::factory()->create();

    $file = File::factory()->create([
        'user_id' => $user->id,
    ]);

    expect($file->user)->toBeInstanceOf(User::class);
    expect($file->user->id)->toBe($user->id);
    expect($file->user_id)->toBe($user->id);
});

test('user has many files', function () {
    $user = User::factory()->create();

    $file1 = File::factory()->create(['user_id' => $user->id]);
    $file2 = File::factory()->create(['user_id' => $user->id]);

    expect($user->files)->toHaveCount(2);
    expect($user->files->pluck('id')->toArray())->toContain($file1->id, $file2->id);
});

test('file uses uuid for route model binding', function () {
    $user = User::factory()->create();
    $file = File::factory()->create(['user_id' => $user->id]);

    expect($file->getRouteKeyName())->toBe('uuid');
    expect(File::where('uuid', $file->uuid)->first()->id)->toBe($file->id);
});

test('file uuid is auto-generated on create', function () {
    $user = User::factory()->create();

    $file = new File([
        'original_filename' => 'test.txt',
        'filename' => 'test123.txt',
        'file_size' => 1024,
        'mime_type' => 'text/plain',
        'user_id' => $user->id,
    ]);
    $file->save();

    expect($file->uuid)->not->toBeNull();
    expect($file->uuid)->toBeString();
    expect($file->uuid)->toMatch('/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i');
});

test('pivot table prevents duplicate file-dataset associations', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);
    $file = File::factory()->create(['user_id' => $user->id]);

    $dataset->files()->attach($file->id);

    expect(fn() => $dataset->files()->attach($file->id))
        ->toThrow(\Illuminate\Database\QueryException::class);
});

test('pivot table includes timestamps', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $dataset = Dataset::factory()->create([
        'owner_id' => $user->id,
        'organisation_id' => $organisation->id,
    ]);
    $file = File::factory()->create(['user_id' => $user->id]);

    $dataset->files()->attach($file->id);

    $pivot = $dataset->files()->first()->pivot;
    expect($pivot->created_at)->not->toBeNull();
    expect($pivot->updated_at)->not->toBeNull();
});
