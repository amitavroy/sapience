<?php

use App\Enums\FileStatus;
use App\Models\Dataset;
use App\Models\File;
use App\Models\Organisation;
use App\Models\User;
use Illuminate\Support\Facades\Config;
use Illuminate\Support\Facades\Storage;

test('organisation member can request file upload URLs', function () {
    // Create a mock disk that supports temporaryUploadUrl
    $mockDisk = \Mockery::mock(\Illuminate\Contracts\Filesystem\Filesystem::class);
    $mockDisk->shouldReceive('temporaryUploadUrl')
        ->andReturn([
            'url' => 'https://example.com/upload',
            'headers' => ['Content-Type' => 'application/octet-stream'],
        ]);

    Storage::shouldReceive('disk')
        ->with('minio')
        ->andReturn($mockDisk);

    Storage::shouldReceive('forgetDisk')
        ->with('minio')
        ->zeroOrMoreTimes()
        ->andReturnNull();

    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $response = $this->actingAs($user)->postJson(
        route('organisations.datasets.files.request-upload', [$organisation, $dataset]),
        [
            'files' => [
                [
                    'original_filename' => 'test1.pdf',
                    'file_size' => 1024,
                    'mime_type' => 'application/pdf',
                ],
                [
                    'original_filename' => 'test2.jpg',
                    'file_size' => 2048,
                    'mime_type' => 'image/jpeg',
                ],
            ],
        ]
    );

    $response->assertSuccessful();
    $response->assertJsonStructure([
        'upload_data' => [
            '*' => ['file_id', 'upload_url', 'headers'],
        ],
    ]);

    // Verify files were created with pending status
    $this->assertDatabaseCount('files', 2);
    $this->assertDatabaseHas('files', [
        'original_filename' => 'test1.pdf',
        'file_size' => 1024,
        'mime_type' => 'application/pdf',
        'status' => FileStatus::Pending->value,
        'user_id' => $user->id,
    ]);

    // Verify files are associated with dataset
    $files = File::whereIn('original_filename', ['test1.pdf', 'test2.jpg'])->get();
    foreach ($files as $file) {
        $this->assertTrue($dataset->files->contains($file->id));
    }
});

test('non-member cannot request file upload URLs', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $response = $this->actingAs($user)->postJson(
        route('organisations.datasets.files.request-upload', [$organisation, $dataset]),
        [
            'files' => [
                [
                    'original_filename' => 'test.pdf',
                    'file_size' => 1024,
                    'mime_type' => 'application/pdf',
                ],
            ],
        ]
    );

    $response->assertForbidden();
});

test('file upload request validates file data', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $response = $this->actingAs($user)->postJson(
        route('organisations.datasets.files.request-upload', [$organisation, $dataset]),
        [
            'files' => [
                [
                    'original_filename' => '',
                    'file_size' => -1,
                    'mime_type' => '',
                ],
            ],
        ]
    );

    $response->assertStatus(422);
    $response->assertJsonValidationErrors(['files.0.original_filename', 'files.0.file_size', 'files.0.mime_type']);
});

test('invalid file is marked as invalid and deleted from S3', function () {
    Storage::fake('s3');
    Config::set('filesystems.default', 's3');
    Config::set('filesystems.uploads_disk', 's3');
    setUploadsDisk('s3');

    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $file = File::factory()->create([
        'user_id' => $user->id,
        'status' => FileStatus::Pending->value,
        'file_size' => 1024,
    ]);
    $dataset->files()->attach($file->id);

    // Create a fake file in S3 with wrong size
    $s3Path = "datasets/{$dataset->id}/files/{$file->filename}";
    Storage::disk('s3')->put($s3Path, str_repeat('a', 2048)); // Wrong size

    $response = $this->actingAs($user)->postJson(
        route('organisations.datasets.files.complete', [$organisation, $dataset]),
        [
            'file_ids' => [$file->id],
        ]
    );

    $response->assertSuccessful();

    // Verify file status was updated to invalid
    $file->refresh();
    $this->assertEquals(FileStatus::Invalid, $file->status);

    // Verify file was deleted from S3
    $this->assertFalse(Storage::disk('s3')->exists($s3Path));
});

test('organisation member can list files with pagination', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $files = File::factory()->count(20)->create(['user_id' => $user->id]);
    $dataset->files()->attach($files->pluck('id'));

    $response = $this->actingAs($user)->getJson(
        route('organisations.datasets.files.index', [$organisation, $dataset]).'?page=1&per_page=10'
    );

    $response->assertSuccessful();
    $response->assertJsonStructure([
        'data',
        'current_page',
        'last_page',
        'per_page',
        'total',
    ]);

    $response->assertJson([
        'current_page' => 1,
        'per_page' => 10,
        'total' => 20,
        'last_page' => 2,
    ]);

    $this->assertCount(10, $response->json('data'));
});

test('organisation member can search files by filename', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $file1 = File::factory()->create([
        'user_id' => $user->id,
        'original_filename' => 'test-document.pdf',
    ]);
    $file2 = File::factory()->create([
        'user_id' => $user->id,
        'original_filename' => 'other-file.jpg',
    ]);
    $dataset->files()->attach([$file1->id, $file2->id]);

    $response = $this->actingAs($user)->getJson(
        route('organisations.datasets.files.index', [$organisation, $dataset]).'?search=test-document'
    );

    $response->assertSuccessful();
    $data = $response->json('data');
    $this->assertCount(1, $data);
    $this->assertEquals('test-document.pdf', $data[0]['original_filename']);
});

test('non-member cannot list files', function () {
    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $response = $this->actingAs($user)->getJson(
        route('organisations.datasets.files.index', [$organisation, $dataset])
    );

    $response->assertForbidden();
});

test('file upload request enforces maximum file size', function () {
    config(['filesystems.max_file_size' => 1000]);

    $user = User::factory()->create();
    $organisation = Organisation::factory()->create();
    $user->organisations()->attach($organisation->id, ['role' => 'member']);

    $dataset = Dataset::factory()->create([
        'organisation_id' => $organisation->id,
        'owner_id' => $user->id,
    ]);

    $response = $this->actingAs($user)->postJson(
        route('organisations.datasets.files.request-upload', [$organisation, $dataset]),
        [
            'files' => [
                [
                    'original_filename' => 'large-file.pdf',
                    'file_size' => 2000, // Exceeds max
                    'mime_type' => 'application/pdf',
                ],
            ],
        ]
    );

    $response->assertStatus(422);
    $response->assertJsonValidationErrors(['files.0.file_size']);
});

test('complete upload only validates files belonging to dataset', function () {
    Storage::fake('s3');
    config(['filesystems.default' => 's3']);

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

    $file1 = File::factory()->create([
        'user_id' => $user->id,
        'status' => FileStatus::Pending->value,
        'file_size' => 1024,
    ]);
    $dataset1->files()->attach($file1->id);

    $file2 = File::factory()->create([
        'user_id' => $user->id,
        'status' => FileStatus::Pending->value,
        'file_size' => 1024,
    ]);
    $dataset2->files()->attach($file2->id);

    // Create fake files in S3
    Storage::disk('s3')->put("datasets/{$dataset1->id}/files/{$file1->filename}", str_repeat('a', 1024));
    Storage::disk('s3')->put("datasets/{$dataset2->id}/files/{$file2->filename}", str_repeat('a', 1024));

    // Try to complete upload for file2 using dataset1 route
    $response = $this->actingAs($user)->postJson(
        route('organisations.datasets.files.complete', [$organisation, $dataset1]),
        [
            'file_ids' => [$file2->id], // File belongs to dataset2, not dataset1
        ]
    );

    $response->assertSuccessful();

    // File2 should not be validated because it doesn't belong to dataset1
    $file2->refresh();
    $this->assertEquals(FileStatus::Pending, $file2->status);
});
